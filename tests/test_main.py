"""
POST /interests — 08-07 호출 경로(07-31). "관심사 등록" 버튼이 부르는 단순 엔드포인트.
interests.py의 CRUD를 몽키패치해 라우팅·분기 로직만 검증 — 실제 DB 파일은 안 건드림.
TestClient(main.app)는 lifespan(AsyncSqliteSaver)도 함께 돈다 — /query와 무관한 엔드포인트
테스트라도 앱을 띄우는 이상 거쳐가는 경로이므로 그대로 둔다(가볍고 실제 파일 I/O만 발생).
"""
import asyncio
import uuid

import fitz
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

import api_keys
import equipment
import interests
import knowledge_notes
import main
import orchestrator
import paper.paper_ingest as paper_ingest
import paper_catalog
import paper_recommend
import research_branches
import research_notes
import research_sessions
import research_workflow


# --- GET/DELETE /query/{thread_id}/messages (08-13 메시지 트리밍 2단계, 수동 삭제) ---
# orchestrator.ParentState.messages를 real 체크포인터에 aupdate_state로 직접 시딩
# (LLM 호출 없음 — /interests/draft 테스트와 같은 패턴). thread_id는 매번 새로 발급.

def test_get_query_messages_returns_role_and_content(monkeypatch):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    with TestClient(main.app) as client:
        asyncio.run(main.app.state.graph.aupdate_state(
            config,
            {"question": "테스트", "messages": [HumanMessage(content="질문"), AIMessage(content="답변")]},
            as_node="__start__",
        ))
        resp = client.get(f"/api/query/{thread_id}/messages")

    assert resp.status_code == 200
    body = resp.json()["messages"]
    assert [m["role"] for m in body] == ["user", "assistant"]
    assert [m["content"] for m in body] == ["질문", "답변"]
    assert all(m["id"] for m in body)  # 실제 체크포인터가 발급한 id(빈 문자열 아님)


def test_get_query_messages_empty_for_fresh_thread(monkeypatch):
    thread_id = str(uuid.uuid4())

    with TestClient(main.app) as client:
        resp = client.get(f"/api/query/{thread_id}/messages")

    assert resp.status_code == 200
    assert resp.json()["messages"] == []


def test_delete_query_message_removes_only_target(monkeypatch):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    with TestClient(main.app) as client:
        asyncio.run(main.app.state.graph.aupdate_state(
            config,
            {"question": "테스트", "messages": [HumanMessage(content="첫 질문"), AIMessage(content="첫 답변"),
                          HumanMessage(content="둘째 질문"), AIMessage(content="둘째 답변")]},
            as_node="__start__",
        ))
        before = client.get(f"/api/query/{thread_id}/messages").json()["messages"]
        target_id = before[0]["id"]  # "첫 질문"

        del_resp = client.delete(f"/api/query/{thread_id}/messages/{target_id}")
        after = client.get(f"/api/query/{thread_id}/messages").json()["messages"]

    assert del_resp.status_code == 200
    assert del_resp.json() == {"deleted_id": target_id}
    assert [m["content"] for m in after] == ["첫 답변", "둘째 질문", "둘째 답변"]  # 지목한 것만 빠짐


# --- GET /interests/draft (08-02, 챗 사이드바 "관심사로 등록" 버튼) ----------------
# orchestrator.draft_interest_from_messages를 몽키패치해 LLM 호출 없이 엔드포인트
# 배관(체크포인트 조회 → 함수 호출 → 응답)만 검증한다. thread_id는 매번 새로 발급해
# 이전 테스트·실제 데이터의 체크포인트와 안 섞이게 한다(빈 상태 → messages=[]).


def test_draft_interest_returns_draft_from_orchestrator(monkeypatch):
    fake_draft = {"title": "위상 물질", "looking_for": "", "already_known": "", "excluded_topics": ""}
    monkeypatch.setattr(
        orchestrator, "draft_interest_from_messages",
        lambda messages, disabled_models=None: (
            fake_draft, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, disabled_models or [],
        ),
    )

    with TestClient(main.app) as client:
        resp = client.get("/api/interests/draft", params={"thread_id": str(uuid.uuid4())})

    assert resp.status_code == 200
    assert resp.json() == fake_draft


def test_draft_interest_passes_thread_messages_to_orchestrator(monkeypatch):
    captured = {}
    def _fake_draft(messages, disabled_models=None):
        captured["messages"] = messages
        empty = {"title": "", "looking_for": "", "already_known": "", "excluded_topics": ""}
        return empty, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, disabled_models or []
    monkeypatch.setattr(orchestrator, "draft_interest_from_messages", _fake_draft)

    with TestClient(main.app) as client:
        client.get("/api/interests/draft", params={"thread_id": str(uuid.uuid4())})

    # 한 번도 실행 안 된(새로 발급한) thread_id라 체크포인트가 비어있음 — messages=[]로 전달돼야 함
    assert captured["messages"] == []


def test_draft_interest_persists_updated_disabled_models(monkeypatch):
    # physics_qa_node와 공유하는 서킷 브레이커 — 첫 호출에서 갱신한 disabled_models가
    # 체크포인트에 반영돼(aupdate_state) 같은 thread의 다음 호출에 그대로 읽혀야 한다.
    seen = []
    def _fake_draft(messages, disabled_models=None):
        seen.append(disabled_models)
        empty = {"title": "", "looking_for": "", "already_known": "", "excluded_topics": ""}
        tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        if len(seen) == 1:
            return empty, tokens, ["gemini"]  # 첫 호출에서 gemini가 소진됐다고 흉내
        return empty, tokens, disabled_models
    monkeypatch.setattr(orchestrator, "draft_interest_from_messages", _fake_draft)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    with TestClient(main.app) as client:
        # 실제로는 /query(물리 QA)가 먼저 돌아 이 thread의 체크포인트를 채워두는데(question 등
        # ParentState 필수 필드), 여기선 QA 그래프를 실제로 안 돌리고 체크포인트만 직접
        # 시드해 가볍게 유지한다 — "한 번도 /query가 안 된 thread"는 별개 케이스(아래
        # test_draft_interest_skips_persist_on_fresh_thread)로 다룬다.
        asyncio.run(main.app.state.graph.aupdate_state(config, {"question": "테스트"}, as_node="__start__"))

        client.get("/api/interests/draft", params={"thread_id": thread_id})
        client.get("/api/interests/draft", params={"thread_id": thread_id})

    assert seen[0] == []
    assert seen[1] == ["gemini"]


def test_draft_interest_skips_persist_on_fresh_thread(monkeypatch):
    # 한 번도 /query가 안 된 thread는 체크포인트가 비어있어(ParentState.question 없음)
    # aupdate_state를 부르면 다음 aget_state가 Pydantic 검증에서 터진다(실제로 재현·확인함) —
    # 이 가드가 없으면 이 테스트의 두 번째 호출에서 그 예외가 그대로 난다.
    def _fake_draft(messages, disabled_models=None):
        empty = {"title": "", "looking_for": "", "already_known": "", "excluded_topics": ""}
        return empty, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, ["gemini"]
    monkeypatch.setattr(orchestrator, "draft_interest_from_messages", _fake_draft)

    thread_id = str(uuid.uuid4())
    with TestClient(main.app) as client:
        first = client.get("/api/interests/draft", params={"thread_id": thread_id})
        second = client.get("/api/interests/draft", params={"thread_id": thread_id})

    assert first.status_code == 200
    assert second.status_code == 200


def test_list_interests_returns_all(monkeypatch):
    fake_rows = [{"id": 1, "title": "양자정보"}, {"id": 2, "title": "응집물질"}]
    monkeypatch.setattr(interests, "list_interests", lambda **kw: fake_rows)

    with TestClient(main.app) as client:
        resp = client.get("/api/interests")

    assert resp.status_code == 200
    assert resp.json() == {"interests": fake_rows}


def test_register_interest_creates_new_when_no_update_id(monkeypatch):
    captured = {}
    def _fake_create(title, looking_for="", already_known="", excluded_topics="", **kw):
        captured.update(title=title, looking_for=looking_for)
        return 42
    monkeypatch.setattr(interests, "create_interest", _fake_create)

    with TestClient(main.app) as client:
        resp = client.post("/api/interests", json={"title": "제목", "looking_for": "찾는것"})

    assert resp.status_code == 200
    assert resp.json() == {"interest_id": 42, "action": "created"}
    assert captured == {"title": "제목", "looking_for": "찾는것"}


def test_register_interest_updates_existing_when_update_id_given(monkeypatch):
    captured = {}
    def _fake_update(interest_id, **fields):
        captured["id"] = interest_id
        captured["fields"] = fields
        return True
    monkeypatch.setattr(interests, "update_interest", _fake_update)

    with TestClient(main.app) as client:
        resp = client.post(
            "/api/interests",
            json={"title": "고친 제목", "looking_for": "", "update_existing_id": 7},
        )

    assert resp.status_code == 200
    assert resp.json() == {"interest_id": 7, "action": "updated"}
    assert captured["id"] == 7
    assert captured["fields"]["title"] == "고친 제목"


def test_register_interest_404_when_update_id_not_found(monkeypatch):
    monkeypatch.setattr(interests, "update_interest", lambda interest_id, **fields: False)

    with TestClient(main.app) as client:
        resp = client.post("/api/interests", json={"title": "제목", "update_existing_id": 999})

    assert resp.status_code == 404


def test_delete_interest_returns_deleted_action(monkeypatch):
    captured = {}
    def _fake_delete(interest_id, **kw):
        captured["id"] = interest_id
        return True
    monkeypatch.setattr(interests, "delete_interest", _fake_delete)
    monkeypatch.setattr(paper_catalog, "delete_screenings_for_interest", lambda interest_id, **kw: None)

    with TestClient(main.app) as client:
        resp = client.delete("/api/interests/7")

    assert resp.status_code == 200
    assert resp.json() == {"interest_id": 7, "action": "deleted"}
    assert captured["id"] == 7


def test_delete_interest_also_deletes_interest_paper_screenings(monkeypatch):
    # 08-04 버그 수정 — 관심사를 지울 때 interest_paper 고아 행이 안 남게 같이 지워야 함.
    monkeypatch.setattr(interests, "delete_interest", lambda interest_id, **kw: True)
    captured = {}
    def _fake_delete_screenings(interest_id, **kw):
        captured["id"] = interest_id
    monkeypatch.setattr(paper_catalog, "delete_screenings_for_interest", _fake_delete_screenings)

    with TestClient(main.app) as client:
        client.delete("/api/interests/7")

    assert captured["id"] == 7


def test_delete_interest_404_when_not_found(monkeypatch):
    monkeypatch.setattr(interests, "delete_interest", lambda interest_id, **kw: False)
    monkeypatch.setattr(paper_catalog, "delete_screenings_for_interest", lambda interest_id, **kw: None)

    with TestClient(main.app) as client:
        resp = client.delete("/api/interests/999")

    assert resp.status_code == 404


# --- POST /interests/{id}/search (08-09③ 호출 경로) -------------------------


def test_trigger_recommend_search_returns_results(monkeypatch):
    fake_results = [{"paper_id": "arxiv:1", "title": "논문", "is_relevant": True}]
    monkeypatch.setattr(paper_recommend, "recommend_for_interest", lambda interest_id, **kw: fake_results)

    with TestClient(main.app) as client:
        resp = client.post("/api/interests/1/search")

    assert resp.status_code == 200
    assert resp.json() == {"recommended": fake_results}


def test_trigger_recommend_search_forwards_start_query_param(monkeypatch):
    # 08-11①, "추가 검색" — 프론트가 넘긴 start를 recommend_for_interest()에 그대로 전달
    captured = {}
    def _fake_recommend(interest_id, **kw):
        captured.update(kw)
        return []
    monkeypatch.setattr(paper_recommend, "recommend_for_interest", _fake_recommend)

    with TestClient(main.app) as client:
        resp = client.post("/api/interests/1/search", params={"start": 5})

    assert resp.status_code == 200
    assert captured["start"] == 5


def test_trigger_recommend_search_404_when_interest_not_found(monkeypatch):
    def _boom(interest_id, **kw):
        raise ValueError(f"관심사 id={interest_id}를 찾을 수 없습니다")
    monkeypatch.setattr(paper_recommend, "recommend_for_interest", _boom)

    with TestClient(main.app) as client:
        resp = client.post("/api/interests/999/search")

    assert resp.status_code == 404


# --- POST /interests/{id}/refresh (08-11② 호출 경로, 관심사 수정 시 자동 재검색) ---


def test_refresh_recommend_search_forwards_existing_candidates(monkeypatch):
    captured = {}
    fake_results = [{"paper_id": "arxiv:1", "is_relevant": True}]
    def _fake_refresh(interest_id, existing_candidates, **kw):
        captured["interest_id"] = interest_id
        captured["existing_candidates"] = existing_candidates
        return fake_results
    monkeypatch.setattr(paper_recommend, "refresh_for_interest", _fake_refresh)

    existing = [{"paper_id": "arxiv:old", "abstract": "초록"}]
    with TestClient(main.app) as client:
        resp = client.post("/api/interests/1/refresh", json={"existing_candidates": existing})

    assert resp.status_code == 200
    assert resp.json() == {"recommended": fake_results}
    assert captured["interest_id"] == 1
    assert captured["existing_candidates"] == existing


def test_refresh_recommend_search_defaults_to_empty_candidates(monkeypatch):
    captured = {}
    def _fake_refresh(interest_id, existing_candidates, **kw):
        captured["existing_candidates"] = existing_candidates
        return []
    monkeypatch.setattr(paper_recommend, "refresh_for_interest", _fake_refresh)

    with TestClient(main.app) as client:
        resp = client.post("/api/interests/1/refresh", json={})

    assert resp.status_code == 200
    assert captured["existing_candidates"] == []


def test_refresh_recommend_search_404_when_interest_not_found(monkeypatch):
    def _boom(interest_id, existing_candidates, **kw):
        raise ValueError(f"관심사 id={interest_id}를 찾을 수 없습니다")
    monkeypatch.setattr(paper_recommend, "refresh_for_interest", _boom)

    with TestClient(main.app) as client:
        resp = client.post("/api/interests/999/refresh", json={})

    assert resp.status_code == 404


# --- GET /interests/{id}/papers (08-03, interest_paper 조인 조회) -----------------


def test_list_interest_papers_returns_results(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: {"id": 1, "title": "관심사"})
    fake_papers = [{"paper_id": "arxiv:1", "is_relevant": True, "title": "논문"}]
    monkeypatch.setattr(paper_catalog, "list_papers_for_interest", lambda interest_id, **kw: fake_papers)

    with TestClient(main.app) as client:
        resp = client.get("/api/interests/1/papers")

    assert resp.status_code == 200
    assert resp.json() == {"papers": fake_papers}


def test_list_interest_papers_forwards_only_relevant_query_param(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: {"id": 1, "title": "관심사"})
    captured = {}
    def _fake_list(interest_id, **kw):
        captured.update(kw)
        return []
    monkeypatch.setattr(paper_catalog, "list_papers_for_interest", _fake_list)

    with TestClient(main.app) as client:
        resp = client.get("/api/interests/1/papers", params={"only_relevant": True})

    assert resp.status_code == 200
    assert captured["only_relevant"] is True


def test_list_interest_papers_404_when_interest_not_found(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: None)

    with TestClient(main.app) as client:
        resp = client.get("/api/interests/999/papers")

    assert resp.status_code == 404


# --- POST /papers (08-11① 호출 경로) -----------------------------------------


def test_register_paper_endpoint_forwards_doi_and_arxiv_id(monkeypatch):
    # register_paper() 자체(파싱·임베딩)는 몽키패치로 갈아끼운다 — 여기서 보는 건
    # 엔드포인트가 업로드 바이트를 임시 파일 경로로 바꿔 doi/arxiv_id와 함께 그대로
    # 넘기고, 반환값을 그대로 응답으로 relay하는지뿐이다.
    captured = {}

    def _fake_register(pdf_path, *, doi=None, arxiv_id=None, filename="", **kw):
        captured["pdf_path"] = pdf_path
        captured["doi"] = doi
        captured["arxiv_id"] = arxiv_id
        captured["filename"] = filename
        return {"paper_id": "arxiv:2401.12345", "text_extractable": True, "chunk_count": 3, "page_count": 1}

    monkeypatch.setattr(paper_ingest, "register_paper", _fake_register)

    with TestClient(main.app) as client:
        resp = client.post(
            "/api/papers",
            files={"file": ("paper.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            data={"arxiv_id": "2401.12345"},
        )

    assert resp.status_code == 200
    assert resp.json() == {
        "paper_id": "arxiv:2401.12345", "text_extractable": True, "chunk_count": 3, "page_count": 1
    }
    assert captured["arxiv_id"] == "2401.12345"
    assert captured["doi"] is None
    assert captured["pdf_path"]  # 임시 파일 경로(내용은 register_paper()가 몽키패치돼 안 쓰임)
    assert captured["filename"] == "paper.pdf"  # 업로드 원본 파일명이 그대로 전달됨


def test_register_paper_endpoint_400_on_invalid_pdf(monkeypatch):
    def _boom(pdf_path, **kw):
        raise fitz.FileDataError("cannot open broken document")

    monkeypatch.setattr(paper_ingest, "register_paper", _boom)

    with TestClient(main.app) as client:
        resp = client.post(
            "/api/papers", files={"file": ("bad.pdf", b"not a pdf at all", "application/pdf")}
        )

    assert resp.status_code == 400


# --- GET /papers (08-11③ 호출 경로) -------------------------------------------


def test_list_papers_forwards_status_filter(monkeypatch):
    captured = {}
    fake_rows = [{"paper_id": "arxiv:1", "status": "recommended"}]

    def _fake_list(*, status=None, **kw):
        captured["status"] = status
        return fake_rows

    monkeypatch.setattr(paper_catalog, "list_papers", _fake_list)

    with TestClient(main.app) as client:
        resp = client.get("/api/papers", params={"status": "recommended"})

    assert resp.status_code == 200
    assert resp.json() == {"papers": fake_rows}
    assert captured["status"] == "recommended"


def test_list_papers_no_filter_returns_all(monkeypatch):
    monkeypatch.setattr(paper_catalog, "list_papers", lambda *, status=None, **kw: [])

    with TestClient(main.app) as client:
        resp = client.get("/api/papers")

    assert resp.status_code == 200
    assert resp.json() == {"papers": []}


def test_list_papers_rejects_invalid_status():
    with TestClient(main.app) as client:
        resp = client.get("/api/papers", params={"status": "bogus"})

    assert resp.status_code == 422


# --- GET /api/library/files (②-A, 08-05) ----------------------------------------
# 얇은 통로 — scan_library_files()가 실제 스캔·traversal 방어를 맡고(test_paper_catalog.py),
# 여기서는 엔드포인트가 그 반환값을 그대로 넘기는지만 확인.


def test_list_library_files_returns_scan_result(monkeypatch):
    fake_files = [{"path": "quantum/foo.pdf", "tracked": True}]
    monkeypatch.setattr(paper_catalog, "scan_library_files", lambda **kw: fake_files)

    with TestClient(main.app) as client:
        resp = client.get("/api/library/files")

    assert resp.status_code == 200
    assert resp.json() == {"files": fake_files}


# --- GET /papers/{paper_id}/summary (08-03) -------------------------------------
# get_paper_summary()는 6-3부터 있었지만 API로 노출된 적이 없었다(main.py 어디서도
# 안 부름) — 여기서 처음 연결.


def test_get_paper_summary_endpoint_returns_extraction(monkeypatch):
    extraction = paper_ingest.PaperExtraction(
        core_claims=["핵심 주장"], evidence=[], author_stated_limitations=[],
        unresolved_questions=[], code_data_availability="",
    )
    monkeypatch.setattr(
        paper_ingest, "get_paper_summary",
        lambda paper_id, **kw: {
            "paper_id": paper_id, "extraction": extraction, "from_cache": True,
            "generated_by": None, "tokens_used": None,
        },
    )

    with TestClient(main.app) as client:
        resp = client.get("/api/papers/arxiv:1/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["from_cache"] is True
    assert body["extraction"]["core_claims"] == ["핵심 주장"]  # PaperExtraction이 dict로 직렬화됨


def test_get_paper_summary_endpoint_404_when_not_registered(monkeypatch):
    def _boom(paper_id, **kw):
        raise ValueError(f"paper_id={paper_id!r}: 등록된 전문 청크가 없음")
    monkeypatch.setattr(paper_ingest, "get_paper_summary", _boom)

    with TestClient(main.app) as client:
        resp = client.get("/api/papers/arxiv:없음/summary")

    assert resp.status_code == 404


def test_get_paper_summary_endpoint_422_when_context_budget_exceeded(monkeypatch):
    from models import ContextBudgetExceeded

    def _boom(paper_id, **kw):
        raise ContextBudgetExceeded("gemini", 999999, 100)
    monkeypatch.setattr(paper_ingest, "get_paper_summary", _boom)

    with TestClient(main.app) as client:
        resp = client.get("/api/papers/arxiv:1/summary")

    assert resp.status_code == 422


# --- /notes (지식 노트, 08-03) — /equipment와 완전히 같은 패턴 -------------------


def test_list_notes_returns_all(monkeypatch):
    fake_notes = [{"id": 1, "title": "노트1", "text": "내용"}]
    monkeypatch.setattr(knowledge_notes, "list_notes", lambda: fake_notes)

    with TestClient(main.app) as client:
        resp = client.get("/api/notes")

    assert resp.status_code == 200
    assert resp.json() == {"notes": fake_notes}


def test_register_note_creates_new_when_no_update_id(monkeypatch):
    captured = {}
    def _fake_create(**fields):
        captured.update(fields)
        return 42
    monkeypatch.setattr(knowledge_notes, "create_note", _fake_create)

    with TestClient(main.app) as client:
        resp = client.post("/api/notes", json={"title": "제목", "text": "본문"})

    assert resp.status_code == 200
    assert resp.json() == {"note_id": 42, "action": "created"}
    assert captured == {"title": "제목", "text": "본문"}


def test_register_note_updates_existing_when_update_id_given(monkeypatch):
    captured = {}
    def _fake_update(note_id, **fields):
        captured["id"] = note_id
        captured["fields"] = fields
        return True
    monkeypatch.setattr(knowledge_notes, "update_note", _fake_update)

    with TestClient(main.app) as client:
        resp = client.post("/api/notes", json={"text": "고친 본문", "update_existing_id": 7})

    assert resp.status_code == 200
    assert resp.json() == {"note_id": 7, "action": "updated"}
    assert captured["id"] == 7
    assert captured["fields"] == {"text": "고친 본문"}


def test_register_note_update_omits_fields_not_sent(monkeypatch):
    captured = {}
    def _fake_update(note_id, **fields):
        captured["fields"] = fields
        return True
    monkeypatch.setattr(knowledge_notes, "update_note", _fake_update)

    with TestClient(main.app) as client:
        client.post("/api/notes", json={"title": "제목만 수정", "update_existing_id": 7})

    assert captured["fields"] == {"title": "제목만 수정"}  # text는 안 보냈으니 안 넘어감


def test_register_note_404_when_update_id_not_found(monkeypatch):
    monkeypatch.setattr(knowledge_notes, "update_note", lambda note_id, **fields: False)

    with TestClient(main.app) as client:
        resp = client.post("/api/notes", json={"title": "이름", "update_existing_id": 999})

    assert resp.status_code == 404


def test_delete_note_endpoint_returns_deleted_action(monkeypatch):
    monkeypatch.setattr(knowledge_notes, "delete_note", lambda note_id: True)

    with TestClient(main.app) as client:
        resp = client.delete("/api/notes/1")

    assert resp.status_code == 200
    assert resp.json() == {"note_id": 1, "action": "deleted"}


def test_delete_note_endpoint_404_when_not_found(monkeypatch):
    monkeypatch.setattr(knowledge_notes, "delete_note", lambda note_id: False)

    with TestClient(main.app) as client:
        resp = client.delete("/api/notes/999")

    assert resp.status_code == 404


# --- /settings/keys (08-05 설정 화면 — 사용자 API 키 입력) --------------------


def test_list_api_key_status_returns_masked_status(monkeypatch):
    fake_status = [
        {"provider": "gemini", "saved": True, "masked_key": "****5678", "updated_at": "2026-08-05T00:00:00+00:00"},
        {"provider": "claude", "saved": False, "masked_key": None, "updated_at": None},
    ]
    monkeypatch.setattr(api_keys, "list_key_status", lambda **kw: fake_status)

    with TestClient(main.app) as client:
        resp = client.get("/api/settings/keys")

    assert resp.status_code == 200
    assert resp.json() == {"keys": fake_status}


def test_save_api_key_calls_set_api_key_with_stripped_value(monkeypatch):
    captured = {}
    def _fake_set(provider, api_key, **kw):
        captured.update(provider=provider, api_key=api_key)
    monkeypatch.setattr(api_keys, "set_api_key", _fake_set)

    with TestClient(main.app) as client:
        resp = client.post("/api/settings/keys", json={"provider": "gemini", "api_key": "  sk-test-1234  "})

    assert resp.status_code == 200
    assert resp.json() == {"provider": "gemini", "action": "saved"}
    assert captured == {"provider": "gemini", "api_key": "sk-test-1234"}  # 앞뒤 공백 제거 확인


def test_save_api_key_rejects_blank_key(monkeypatch):
    monkeypatch.setattr(api_keys, "set_api_key", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("호출되면 안 됨")))

    with TestClient(main.app) as client:
        resp = client.post("/api/settings/keys", json={"provider": "gemini", "api_key": "   "})

    assert resp.status_code == 400


def test_save_api_key_rejects_unsupported_provider():
    with TestClient(main.app) as client:
        resp = client.post("/api/settings/keys", json={"provider": "qwen-tuned", "api_key": "irrelevant"})

    assert resp.status_code == 422  # Literal["gemini", "claude"] 밖의 값 — FastAPI 검증에서 거부


def test_delete_api_key_endpoint_returns_deleted_action(monkeypatch):
    monkeypatch.setattr(api_keys, "delete_api_key", lambda provider: True)

    with TestClient(main.app) as client:
        resp = client.delete("/api/settings/keys/gemini")

    assert resp.status_code == 200
    assert resp.json() == {"provider": "gemini", "action": "deleted"}


def test_delete_api_key_endpoint_404_when_not_found(monkeypatch):
    monkeypatch.setattr(api_keys, "delete_api_key", lambda provider: False)

    with TestClient(main.app) as client:
        resp = client.delete("/api/settings/keys/claude")

    assert resp.status_code == 404


# --- /equipment (실험도구 DB ⑤, /interests와 완전히 같은 패턴) -----------------


def test_list_equipment_returns_all(monkeypatch):
    fake_rows = [{"id": 1, "name": "오실로스코프"}, {"id": 2, "name": "레이저"}]
    monkeypatch.setattr(equipment, "list_equipment", lambda **kw: fake_rows)

    with TestClient(main.app) as client:
        resp = client.get("/api/equipment")

    assert resp.status_code == 200
    assert resp.json() == {"equipment": fake_rows}


def test_register_equipment_creates_new_when_no_update_id(monkeypatch):
    captured = {}
    def _fake_create(name, **fields):
        captured.update(name=name, fields=fields)
        return 42
    monkeypatch.setattr(equipment, "create_equipment", _fake_create)

    with TestClient(main.app) as client:
        resp = client.post(
            "/api/equipment",
            json={"name": "오실로스코프", "purpose": "파형 관찰", "precautions": "정격 초과 금지"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"equipment_id": 42, "action": "created"}
    assert captured["name"] == "오실로스코프"
    assert captured["fields"]["purpose"] == "파형 관찰"
    assert captured["fields"]["precautions"] == "정격 초과 금지"  # 안전 정보가 실제로 전달되는지


def test_register_equipment_updates_existing_when_update_id_given(monkeypatch):
    captured = {}
    def _fake_update(equipment_id, **fields):
        captured["id"] = equipment_id
        captured["fields"] = fields
        return True
    monkeypatch.setattr(equipment, "update_equipment", _fake_update)

    with TestClient(main.app) as client:
        resp = client.post(
            "/api/equipment",
            json={"name": "고친 이름", "purpose": "", "update_existing_id": 7},
        )

    assert resp.status_code == 200
    assert resp.json() == {"equipment_id": 7, "action": "updated"}
    assert captured["id"] == 7
    assert captured["fields"]["name"] == "고친 이름"


def test_register_equipment_update_omits_fields_not_sent(monkeypatch):
    # 이름만 고쳐 보낸 요청이 등록해둔 precautions(안전 주의사항)를 ""로 덮어쓰면 안 된다 —
    # 보내지 않은 필드는 update_equipment()에 아예 안 넘어가야 기존 값이 유지된다.
    captured = {}
    def _fake_update(equipment_id, **fields):
        captured["fields"] = fields
        return True
    monkeypatch.setattr(equipment, "update_equipment", _fake_update)

    with TestClient(main.app) as client:
        resp = client.post("/api/equipment", json={"name": "고친 이름", "update_existing_id": 7})

    assert resp.status_code == 200
    assert captured["fields"] == {"name": "고친 이름"}  # purpose/detail/precautions는 없음


def test_register_equipment_update_can_clear_field_when_explicitly_empty(monkeypatch):
    # "명시 안 함"(None)과 "빈 값으로 설정"(""))의 구분 — 빈 문자열을 실제로 보내면
    # 지우는 게 맞다(위 테스트가 막는 건 안 보낸 필드가 지워지는 것뿐).
    captured = {}
    def _fake_update(equipment_id, **fields):
        captured["fields"] = fields
        return True
    monkeypatch.setattr(equipment, "update_equipment", _fake_update)

    with TestClient(main.app) as client:
        client.post("/api/equipment", json={"name": "이름", "precautions": "", "update_existing_id": 7})

    assert captured["fields"]["precautions"] == ""


def test_register_equipment_404_when_update_id_not_found(monkeypatch):
    monkeypatch.setattr(equipment, "update_equipment", lambda equipment_id, **fields: False)

    with TestClient(main.app) as client:
        resp = client.post("/api/equipment", json={"name": "이름", "update_existing_id": 999})

    assert resp.status_code == 404


def test_delete_equipment_returns_deleted_action(monkeypatch):
    captured = {}
    def _fake_delete(equipment_id, **kw):
        captured["id"] = equipment_id
        return True
    monkeypatch.setattr(equipment, "delete_equipment", _fake_delete)

    with TestClient(main.app) as client:
        resp = client.delete("/api/equipment/7")

    assert resp.status_code == 200
    assert resp.json() == {"equipment_id": 7, "action": "deleted"}
    assert captured["id"] == 7


def test_delete_equipment_404_when_not_found(monkeypatch):
    monkeypatch.setattr(equipment, "delete_equipment", lambda equipment_id, **kw: False)

    with TestClient(main.app) as client:
        resp = client.delete("/api/equipment/999")


# --- 연구 워크플로우(⑥) 세션·advance 엔드포인트 ------------------------------------
# research_workflow.graph 자체(노드 로직)는 test_research_workflow.py가 이미 검증한다.
# 여기선 app.state.research_graph를 가짜로 바꿔치기해 배관(세션 생성·stage 갱신·
# 에러 분기)만 본다 — 실제 그래프를 태우면 LLM 호출까지 물어와 톨게이트 원칙에 어긋난다.
class _FakeSnapshot:
    def __init__(self, checkpoint_id, values, next=(), created_at="2026-08-04T00:00:00+00:00", source="loop"):
        self.config = {"configurable": {"checkpoint_id": checkpoint_id}}
        self.values = values
        self.next = next
        self.created_at = created_at
        self.metadata = {"source": source}


class _FakeResearchGraph:
    def __init__(self, result, checkpoints=None, history=None):
        self.result = result  # checkpoint_id 없이 조회하면(=tip) 이 값
        self.checkpoints = checkpoints or {}  # checkpoint_id -> values (복원 테스트용)
        self.history = history or []  # aget_state_history가 그대로 순서대로 내보낼 _FakeSnapshot 목록
        self.invoked_with = None
        self.updated_state = None

    async def ainvoke(self, inputs, config):
        self.invoked_with = (inputs, config)
        return self.result

    async def aget_state(self, config):
        checkpoint_id = config["configurable"].get("checkpoint_id")
        class _Snapshot:
            pass
        snapshot = _Snapshot()
        snapshot.values = self.checkpoints.get(checkpoint_id, {}) if checkpoint_id else self.result
        # checkpoint_id 없이 조회하면(=tip 재조회) advance_research()가 복원 경로에서
        # 새 turn-final 체크포인트 id를 얻으려고 다시 부르는 호출과 짝을 맞춘다.
        snapshot.config = {"configurable": {"checkpoint_id": checkpoint_id or "new-tip-cp"}}
        return snapshot

    async def aupdate_state(self, config, values, as_node=None):
        self.updated_state = values
        self.result = {**self.result, **values}  # /draft가 곧바로 aget_state로 재조회하는 것과 맞춰 병합 흉내

    async def aget_state_history(self, config):
        for snapshot in self.history:
            yield snapshot


def test_advance_research_rejects_new_thread_without_topic(monkeypatch):
    monkeypatch.setattr(research_sessions, "get_session", lambda thread_id, **kw: None)

    with TestClient(main.app) as client:
        resp = client.post(f"/api/research/{uuid.uuid4()}/advance", json={"stage": "hypothesis"})

    assert resp.status_code == 400


def test_advance_research_rejects_new_thread_with_non_hypothesis_stage(monkeypatch):
    monkeypatch.setattr(research_sessions, "get_session", lambda thread_id, **kw: None)

    with TestClient(main.app) as client:
        resp = client.post(
            f"/api/research/{uuid.uuid4()}/advance", json={"stage": "design", "topic": "주제"}
        )

    assert resp.status_code == 400


def test_advance_research_creates_session_on_first_call(monkeypatch):
    monkeypatch.setattr(research_sessions, "get_session", lambda thread_id, **kw: None)
    created = {}
    monkeypatch.setattr(
        research_sessions, "create_session",
        lambda thread_id, title, topic, stage, **kw: created.update(
            thread_id=thread_id, title=title, topic=topic, stage=stage
        ),
    )
    monkeypatch.setattr(research_sessions, "update_stage", lambda thread_id, stage, **kw: True)
    fake_graph = _FakeResearchGraph({"stage": "hypothesis", "hypothesis": "테스트 가설"})

    thread_id = str(uuid.uuid4())
    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph  # lifespan이 컴파일한 진짜 그래프를 가짜로 교체
        resp = client.post(
            f"/api/research/{thread_id}/advance",
            json={"stage": "hypothesis", "topic": "그래핀 전도도"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"stage": "hypothesis", "hypothesis": "테스트 가설"}
    assert created == {
        "thread_id": thread_id, "title": "그래핀 전도도", "topic": "그래핀 전도도", "stage": "hypothesis",
    }
    assert fake_graph.invoked_with[0] == {"stage": "hypothesis", "topic": "그래핀 전도도"}


def test_advance_research_passes_user_guidance_through(monkeypatch):
    # 재생성 시 방향 지시(+프론트가 조립한 직접 수정 내용)가 ainvoke 입력에 실려가야
    # generate_hypothesis 등이 프롬프트에 끼워 넣을 수 있다.
    fake_session = {"thread_id": "t1", "title": "제목", "topic": "주제", "stage": "design"}
    monkeypatch.setattr(research_sessions, "get_session", lambda thread_id, **kw: fake_session)
    monkeypatch.setattr(research_sessions, "update_stage", lambda thread_id, stage, **kw: True)
    fake_graph = _FakeResearchGraph({"stage": "design"})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.post("/api/research/t1/advance", json={"stage": "design", "user_guidance": "더 간단한 장비로"})

    assert resp.status_code == 200
    assert fake_graph.invoked_with[0] == {"stage": "design", "user_guidance": "더 간단한 장비로"}


def test_advance_research_omits_user_guidance_when_not_given(monkeypatch):
    fake_session = {"thread_id": "t1", "title": "제목", "topic": "주제", "stage": "design"}
    monkeypatch.setattr(research_sessions, "get_session", lambda thread_id, **kw: fake_session)
    monkeypatch.setattr(research_sessions, "update_stage", lambda thread_id, stage, **kw: True)
    fake_graph = _FakeResearchGraph({"stage": "design"})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.post("/api/research/t1/advance", json={"stage": "design"})

    assert "user_guidance" not in fake_graph.invoked_with[0]


def test_advance_research_does_not_recreate_existing_session(monkeypatch):
    fake_session = {"thread_id": "t1", "title": "제목", "topic": "주제", "stage": "hypothesis"}
    monkeypatch.setattr(research_sessions, "get_session", lambda thread_id, **kw: fake_session)
    create_calls = []
    monkeypatch.setattr(research_sessions, "create_session", lambda *a, **kw: create_calls.append(1))
    monkeypatch.setattr(research_sessions, "update_stage", lambda thread_id, stage, **kw: True)
    fake_graph = _FakeResearchGraph({"stage": "design"})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.post("/api/research/t1/advance", json={"stage": "design"})

    assert resp.status_code == 200
    assert create_calls == []
    # topic을 안 보냈으니 ainvoke 입력에도 topic 키가 없어야 함(기존 체크포인트 값 유지)
    assert fake_graph.invoked_with[0] == {"stage": "design"}


def test_advance_research_updates_session_stage_after_invoke(monkeypatch):
    fake_session = {"thread_id": "t1", "title": "제목", "topic": "주제", "stage": "hypothesis"}
    monkeypatch.setattr(research_sessions, "get_session", lambda thread_id, **kw: fake_session)
    stage_updates = []
    monkeypatch.setattr(
        research_sessions, "update_stage",
        lambda thread_id, stage, **kw: stage_updates.append((thread_id, stage)),
    )
    fake_graph = _FakeResearchGraph({"stage": "design"})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        client.post("/api/research/t1/advance", json={"stage": "design"})

    assert stage_updates == [("t1", "design")]


def test_get_research_state_returns_snapshot_values(monkeypatch):
    fake_graph = _FakeResearchGraph({"stage": "design", "hypothesis": "가설"})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.get("/api/research/t1")

    assert resp.status_code == 200
    assert resp.json() == {"stage": "design", "hypothesis": "가설"}


def test_get_research_state_404_when_no_checkpoint(monkeypatch):
    fake_graph = _FakeResearchGraph({})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.get("/api/research/no-such-thread")

    assert resp.status_code == 404


def test_list_research_sessions_returns_all(monkeypatch):
    fake_rows = [{"thread_id": "t1", "title": "연구1"}, {"thread_id": "t2", "title": "연구2"}]
    monkeypatch.setattr(research_sessions, "list_sessions", lambda **kw: fake_rows)

    with TestClient(main.app) as client:
        resp = client.get("/api/research/sessions")

    assert resp.status_code == 200
    assert resp.json() == {"sessions": fake_rows}


def test_rename_research_session_updates_title(monkeypatch):
    captured = {}
    def _fake_update(thread_id, title, **kw):
        captured["args"] = (thread_id, title)
        return True
    monkeypatch.setattr(research_sessions, "update_title", _fake_update)

    with TestClient(main.app) as client:
        resp = client.post("/api/research/sessions/t1/title", json={"title": "새 제목"})

    assert resp.status_code == 200
    assert captured["args"] == ("t1", "새 제목")


def test_rename_research_session_404_when_not_found(monkeypatch):
    monkeypatch.setattr(research_sessions, "update_title", lambda thread_id, title, **kw: False)

    with TestClient(main.app) as client:
        resp = client.post("/api/research/sessions/no-such-thread/title", json={"title": "새 제목"})

    assert resp.status_code == 404


def test_close_research_session_deletes_row(monkeypatch):
    captured = {}
    def _fake_delete(thread_id, **kw):
        captured["thread_id"] = thread_id
        return True
    monkeypatch.setattr(research_sessions, "delete_session", _fake_delete)

    with TestClient(main.app) as client:
        resp = client.delete("/api/research/sessions/t1")

    assert resp.status_code == 200
    assert resp.json() == {"thread_id": "t1", "action": "deleted"}
    assert captured["thread_id"] == "t1"


def test_close_research_session_404_when_not_found(monkeypatch):
    monkeypatch.setattr(research_sessions, "delete_session", lambda thread_id, **kw: False)

    with TestClient(main.app) as client:
        resp = client.delete("/api/research/sessions/no-such-thread")

    assert resp.status_code == 404


# --- 체크포인트 히스토리·복원(08-04 후속, "탭처럼 왔다갔다") -----------------------

def test_advance_research_from_checkpoint_restores_past_values(monkeypatch):
    fake_session = {"thread_id": "t1", "title": "제목", "topic": "주제", "stage": "design"}
    monkeypatch.setattr(research_sessions, "get_session", lambda thread_id, **kw: fake_session)
    monkeypatch.setattr(research_sessions, "update_stage", lambda thread_id, stage, **kw: True)
    recorded_branches = []
    monkeypatch.setattr(
        research_branches, "record_branch",
        lambda child_checkpoint_id, source_checkpoint_id, thread_id, **kw: recorded_branches.append(
            (child_checkpoint_id, source_checkpoint_id, thread_id)
        ),
    )

    past_values = {
        "stage": "hypothesis", "hypothesis": "옛 가설",
        "references": [{"paper_id": "p1", "title": "A", "source": "owned", "reasoning": ""}],
    }
    tip_values = {
        "stage": "design",
        "references": [
            {"paper_id": "p1", "title": "A", "source": "owned", "reasoning": ""},
            {"paper_id": "p2", "title": "B", "source": "external", "reasoning": "관련 있음"},
        ],
    }
    fake_graph = _FakeResearchGraph(tip_values, checkpoints={"cp1": past_values})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.post(
            "/api/research/t1/advance",
            json={"stage": "design", "from_checkpoint_id": "cp1", "keep_reference_paper_ids": ["p2"]},
        )

    assert resp.status_code == 200
    # 과거 값(hypothesis)이 복원되고, references는 과거 것 + 남기기로 고른 p2만 합쳐짐
    assert fake_graph.updated_state["hypothesis"] == "옛 가설"
    assert [r["paper_id"] for r in fake_graph.updated_state["references"]] == ["p1", "p2"]
    # 복원 후 이어지는 ainvoke는 checkpoint_id 없는 tip config로(새로 만든 tip에서 진행)
    assert "checkpoint_id" not in fake_graph.invoked_with[1]["configurable"]
    # 이 턴이 cp1에서 갈라졌다는 게 research_branches에 기록됨(새 tip은 가짜 그래프의
    # aget_state가 내주는 "new-tip-cp")
    assert recorded_branches == [("new-tip-cp", "cp1", "t1")]


def test_advance_research_from_checkpoint_defaults_to_dropping_new_references(monkeypatch):
    fake_session = {"thread_id": "t1", "title": "제목", "topic": "주제", "stage": "design"}
    monkeypatch.setattr(research_sessions, "get_session", lambda thread_id, **kw: fake_session)
    monkeypatch.setattr(research_sessions, "update_stage", lambda thread_id, stage, **kw: True)
    monkeypatch.setattr(research_branches, "record_branch", lambda **kw: None)

    past_values = {"stage": "hypothesis", "references": [{"paper_id": "p1", "title": "A", "source": "owned", "reasoning": ""}]}
    tip_values = {
        "stage": "design",
        "references": [
            {"paper_id": "p1", "title": "A", "source": "owned", "reasoning": ""},
            {"paper_id": "p2", "title": "B", "source": "external", "reasoning": ""},
        ],
    }
    fake_graph = _FakeResearchGraph(tip_values, checkpoints={"cp1": past_values})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        # keep_reference_paper_ids를 안 보냄 — 기본값(빈 리스트)
        client.post("/api/research/t1/advance", json={"stage": "design", "from_checkpoint_id": "cp1"})

    assert [r["paper_id"] for r in fake_graph.updated_state["references"]] == ["p1"]


def test_advance_research_404_when_from_checkpoint_not_found(monkeypatch):
    fake_session = {"thread_id": "t1", "title": "제목", "topic": "주제", "stage": "design"}
    monkeypatch.setattr(research_sessions, "get_session", lambda thread_id, **kw: fake_session)
    fake_graph = _FakeResearchGraph({"stage": "design"}, checkpoints={})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.post("/api/research/t1/advance", json={"stage": "design", "from_checkpoint_id": "no-such-cp"})

    assert resp.status_code == 404


def test_get_research_history_keeps_only_turn_final_snapshots_oldest_first(monkeypatch):
    monkeypatch.setattr(research_branches, "get_sources", lambda ids, **kw: {})
    monkeypatch.setattr(research_notes, "get_notes_for_checkpoints", lambda ids, **kw: {})
    history = [  # aget_state_history는 최신순으로 내놓음
        _FakeSnapshot("c3", {"stage": "design"}, next=(), created_at="t3"),
        _FakeSnapshot("c2b", {"stage": "hypothesis"}, next=("find_hypothesis_references",), created_at="t2b"),
        _FakeSnapshot("c2", {"stage": "hypothesis"}, next=(), created_at="t2"),
        _FakeSnapshot("c1", {"stage": "hypothesis"}, next=(), created_at="t1"),
    ]
    fake_graph = _FakeResearchGraph({}, history=history)

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.get("/api/research/t1/history")

    assert resp.status_code == 200
    ids = [e["checkpoint_id"] for e in resp.json()["history"]]
    assert ids == ["c1", "c2", "c3"]  # c2b(진행 중 체크포인트)는 빠지고, 오래된 것부터


def test_get_research_history_includes_latest_pure_edit_checkpoint(monkeypatch):
    # /draft로 값만 주입한 체크포인트는 next가 안 비어있지만(toy 그래프로 실제 확인),
    # 그게 최신(index 0)이면 사용자가 방금 저장한 편집본이라 탭에 보여야 한다.
    monkeypatch.setattr(research_branches, "get_sources", lambda ids, **kw: {})
    monkeypatch.setattr(research_notes, "get_notes_for_checkpoints", lambda ids, **kw: {})
    history = [
        _FakeSnapshot("c2edit", {"stage": "writing"}, next=("draft_paper",), created_at="t2", source="update"),
        _FakeSnapshot("c1", {"stage": "writing"}, next=(), created_at="t1", source="loop"),
    ]
    fake_graph = _FakeResearchGraph({}, history=history)

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.get("/api/research/t1/history")

    ids = [e["checkpoint_id"] for e in resp.json()["history"]]
    assert ids == ["c1", "c2edit"]


def test_get_research_history_attaches_branch_source(monkeypatch):
    # research_branches에 기록이 있으면 그 entry에 branched_from_checkpoint_id로
    # 붙고, 기록이 없는 entry는 None — parent_config가 아니라 이 사이드테이블이
    # 계보 정보의 유일한 출처다(설계 노트 참고).
    monkeypatch.setattr(
        research_branches, "get_sources", lambda ids, **kw: {"c2": "c1"} if "c2" in ids else {}
    )
    monkeypatch.setattr(research_notes, "get_notes_for_checkpoints", lambda ids, **kw: {})
    history = [
        _FakeSnapshot("c2", {"stage": "hypothesis"}, next=(), created_at="t2"),
        _FakeSnapshot("c1", {"stage": "design"}, next=(), created_at="t1"),
    ]
    fake_graph = _FakeResearchGraph({}, history=history)

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.get("/api/research/t1/history")

    entries = {e["checkpoint_id"]: e["branched_from_checkpoint_id"] for e in resp.json()["history"]}
    assert entries == {"c1": None, "c2": "c1"}


def test_get_research_history_attaches_notes(monkeypatch):
    monkeypatch.setattr(research_branches, "get_sources", lambda ids, **kw: {})
    monkeypatch.setattr(
        research_notes, "get_notes_for_checkpoints", lambda ids, **kw: {"c1": "장비 다시 확인"} if "c1" in ids else {}
    )
    history = [
        _FakeSnapshot("c2", {"stage": "design"}, next=(), created_at="t2"),
        _FakeSnapshot("c1", {"stage": "hypothesis"}, next=(), created_at="t1"),
    ]
    fake_graph = _FakeResearchGraph({}, history=history)

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.get("/api/research/t1/history")

    notes = {e["checkpoint_id"]: e["note"] for e in resp.json()["history"]}
    assert notes == {"c1": "장비 다시 확인", "c2": ""}  # 메모 없으면 빈 문자열


def test_get_research_history_excludes_stale_edit_checkpoint(monkeypatch):
    # 편집(update) 체크포인트가 최신이 아니면(그 뒤에 진짜 advance가 또 일어났으면)
    # 이미 그 advance의 최종 결과가 next==()로 잡히니 굳이 또 보여줄 필요가 없다.
    monkeypatch.setattr(research_branches, "get_sources", lambda ids, **kw: {})
    monkeypatch.setattr(research_notes, "get_notes_for_checkpoints", lambda ids, **kw: {})
    history = [
        _FakeSnapshot("c3", {"stage": "writing"}, next=(), created_at="t3", source="loop"),
        _FakeSnapshot("c2edit", {"stage": "writing"}, next=("draft_paper",), created_at="t2", source="update"),
        _FakeSnapshot("c1", {"stage": "writing"}, next=(), created_at="t1", source="loop"),
    ]
    fake_graph = _FakeResearchGraph({}, history=history)

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.get("/api/research/t1/history")

    ids = [e["checkpoint_id"] for e in resp.json()["history"]]
    assert ids == ["c1", "c3"]  # c2edit(더 이상 최신이 아닌 편집본)는 빠짐


# --- 논문 초안 인앱 편집(08-04 후속) -----------------------------------------------

def test_update_research_draft_merges_given_fields_only(monkeypatch):
    fake_graph = _FakeResearchGraph({"stage": "writing", "title": "옛 제목", "abstract": "옛 초록"})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.post("/api/research/t1/draft", json={"title": "새 제목"})

    assert resp.status_code == 200
    assert fake_graph.updated_state == {"title": "새 제목"}  # abstract 등 안 보낸 필드는 안 실림
    assert resp.json()["title"] == "새 제목"
    assert resp.json()["abstract"] == "옛 초록"  # 안 건드린 필드는 그대로


def test_update_research_draft_400_when_not_writing_stage(monkeypatch):
    fake_graph = _FakeResearchGraph({"stage": "design"})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.post("/api/research/t1/draft", json={"title": "새 제목"})

    assert resp.status_code == 400
    assert fake_graph.updated_state is None


def test_update_research_draft_404_when_no_state(monkeypatch):
    fake_graph = _FakeResearchGraph({})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.post("/api/research/t1/draft", json={"title": "새 제목"})

    assert resp.status_code == 404


def test_update_research_draft_skips_update_when_no_fields_given(monkeypatch):
    fake_graph = _FakeResearchGraph({"stage": "writing", "title": "제목"})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.post("/api/research/t1/draft", json={})

    assert resp.status_code == 200
    assert fake_graph.updated_state is None  # 빈 요청으로 불필요한 체크포인트를 안 만듦


# --- 참고문헌만 독립 재시도 (08-04 후속, Part B) -----------------------------------

def test_retry_research_references_404_when_no_state(monkeypatch):
    fake_graph = _FakeResearchGraph({})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.post("/api/research/t1/references/retry")

    assert resp.status_code == 404


def test_retry_research_references_400_for_stage_without_reference_node(monkeypatch):
    # report/writing은 REFERENCE_NODE_BY_STAGE에 없음 — compile_experiment_report/
    # draft_paper는 새 텍스트를 안 만들어 검색할 새 주장이 없다(research_workflow.py 참고).
    fake_graph = _FakeResearchGraph({"topic": "주제", "stage": "writing"})

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.post("/api/research/t1/references/retry")

    assert resp.status_code == 400


def test_retry_research_references_calls_matching_node_and_persists(monkeypatch):
    captured = {}

    def _fake_design_node(state):
        captured["procedure"] = state.procedure
        return {
            "references": [{"paper_id": "p1", "title": "새 논문", "source": "external", "reasoning": "관련"}],
            "comment": "새로 찾음",
        }
    monkeypatch.setitem(research_workflow.REFERENCE_NODE_BY_STAGE, "design", _fake_design_node)

    def _boom_hypothesis_node(state):
        raise AssertionError("stage=design인데 hypothesis 노드가 불리면 안 됨")
    monkeypatch.setitem(research_workflow.REFERENCE_NODE_BY_STAGE, "hypothesis", _boom_hypothesis_node)

    fake_graph = _FakeResearchGraph({
        "topic": "주제", "stage": "design", "hypothesis": "가설",
        "procedure": "1. 실험한다", "comment": "이전 안내", "references": [],
    })

    with TestClient(main.app) as client:
        main.app.state.research_graph = fake_graph
        resp = client.post("/api/research/t1/references/retry")

    assert resp.status_code == 200
    assert captured["procedure"] == "1. 실험한다"  # tip 값으로 WorkflowState가 재구성됨
    # 그래프를 안 타고 aupdate_state(as_node="__start__")로 결과만 tip에 얹음(/draft와 같은 패턴)
    assert fake_graph.updated_state == {
        "references": [{"paper_id": "p1", "title": "새 논문", "source": "external", "reasoning": "관련"}],
        "comment": "새로 찾음",
    }
    body = resp.json()
    assert body["comment"] == "새로 찾음"
    assert body["references"][0]["paper_id"] == "p1"
    assert body["procedure"] == "1. 실험한다"  # 설계 산출물 자체는 안 건드림


# --- 단계별 메모 (08-04 후속, "타임라인·체크 결합(브랜치형)" 설계 노트 §단계별 메모) --------

def test_save_research_note_calls_set_note(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        research_notes, "set_note",
        lambda checkpoint_id, thread_id, note, **kw: captured.update(
            checkpoint_id=checkpoint_id, thread_id=thread_id, note=note
        ),
    )

    with TestClient(main.app) as client:
        resp = client.post("/api/research/t1/notes/c1", json={"note": "장비 다시 확인"})

    assert resp.status_code == 200
    assert captured == {"checkpoint_id": "c1", "thread_id": "t1", "note": "장비 다시 확인"}
    assert resp.json() == {"checkpoint_id": "c1", "note": "장비 다시 확인"}


def test_save_research_note_with_empty_string_clears_it(monkeypatch):
    # research_notes.set_note 자체가 빈 문자열=삭제를 처리한다(test_research_notes.py에서
    # 이미 검증) — 여기선 엔드포인트가 그 값을 그대로 전달만 하는지만 본다.
    captured = {}
    monkeypatch.setattr(
        research_notes, "set_note",
        lambda checkpoint_id, thread_id, note, **kw: captured.update(note=note),
    )

    with TestClient(main.app) as client:
        resp = client.post("/api/research/t1/notes/c1", json={"note": ""})

    assert resp.status_code == 200
    assert captured["note"] == ""
