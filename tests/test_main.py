"""
POST /interests — 08-07 호출 경로(07-31). "관심사 등록" 버튼이 부르는 단순 엔드포인트.
interests.py의 CRUD를 몽키패치해 라우팅·분기 로직만 검증 — 실제 DB 파일은 안 건드림.
TestClient(main.app)는 lifespan(AsyncSqliteSaver)도 함께 돈다 — /query와 무관한 엔드포인트
테스트라도 앱을 띄우는 이상 거쳐가는 경로이므로 그대로 둔다(가볍고 실제 파일 I/O만 발생).
"""
import fitz
from fastapi.testclient import TestClient

import interests
import main
import paper.paper_ingest as paper_ingest
import paper_catalog
import paper_recommend


def test_list_interests_returns_all(monkeypatch):
    fake_rows = [{"id": 1, "title": "양자정보"}, {"id": 2, "title": "응집물질"}]
    monkeypatch.setattr(interests, "list_interests", lambda **kw: fake_rows)

    with TestClient(main.app) as client:
        resp = client.get("/interests")

    assert resp.status_code == 200
    assert resp.json() == {"interests": fake_rows}


def test_register_interest_creates_new_when_no_update_id(monkeypatch):
    captured = {}
    def _fake_create(title, looking_for="", already_known="", excluded_topics="", **kw):
        captured.update(title=title, looking_for=looking_for)
        return 42
    monkeypatch.setattr(interests, "create_interest", _fake_create)

    with TestClient(main.app) as client:
        resp = client.post("/interests", json={"title": "제목", "looking_for": "찾는것"})

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
            "/interests",
            json={"title": "고친 제목", "looking_for": "", "update_existing_id": 7},
        )

    assert resp.status_code == 200
    assert resp.json() == {"interest_id": 7, "action": "updated"}
    assert captured["id"] == 7
    assert captured["fields"]["title"] == "고친 제목"


def test_register_interest_404_when_update_id_not_found(monkeypatch):
    monkeypatch.setattr(interests, "update_interest", lambda interest_id, **fields: False)

    with TestClient(main.app) as client:
        resp = client.post("/interests", json={"title": "제목", "update_existing_id": 999})

    assert resp.status_code == 404


def test_delete_interest_returns_deleted_action(monkeypatch):
    captured = {}
    def _fake_delete(interest_id, **kw):
        captured["id"] = interest_id
        return True
    monkeypatch.setattr(interests, "delete_interest", _fake_delete)

    with TestClient(main.app) as client:
        resp = client.delete("/interests/7")

    assert resp.status_code == 200
    assert resp.json() == {"interest_id": 7, "action": "deleted"}
    assert captured["id"] == 7


def test_delete_interest_404_when_not_found(monkeypatch):
    monkeypatch.setattr(interests, "delete_interest", lambda interest_id, **kw: False)

    with TestClient(main.app) as client:
        resp = client.delete("/interests/999")

    assert resp.status_code == 404


# --- POST /interests/{id}/search (08-09③ 호출 경로) -------------------------


def test_trigger_recommend_search_returns_results(monkeypatch):
    fake_results = [{"paper_id": "arxiv:1", "title": "논문", "is_relevant": True}]
    monkeypatch.setattr(paper_recommend, "recommend_for_interest", lambda interest_id, **kw: fake_results)

    with TestClient(main.app) as client:
        resp = client.post("/interests/1/search")

    assert resp.status_code == 200
    assert resp.json() == {"recommended": fake_results}


def test_trigger_recommend_search_404_when_interest_not_found(monkeypatch):
    def _boom(interest_id, **kw):
        raise ValueError(f"관심사 id={interest_id}를 찾을 수 없습니다")
    monkeypatch.setattr(paper_recommend, "recommend_for_interest", _boom)

    with TestClient(main.app) as client:
        resp = client.post("/interests/999/search")

    assert resp.status_code == 404


# --- POST /papers (08-11① 호출 경로) -----------------------------------------


def test_register_paper_endpoint_forwards_doi_and_arxiv_id(monkeypatch):
    # register_paper() 자체(파싱·임베딩)는 몽키패치로 갈아끼운다 — 여기서 보는 건
    # 엔드포인트가 업로드 바이트를 임시 파일 경로로 바꿔 doi/arxiv_id와 함께 그대로
    # 넘기고, 반환값을 그대로 응답으로 relay하는지뿐이다.
    captured = {}

    def _fake_register(pdf_path, *, doi=None, arxiv_id=None, **kw):
        captured["pdf_path"] = pdf_path
        captured["doi"] = doi
        captured["arxiv_id"] = arxiv_id
        return {"paper_id": "arxiv:2401.12345", "text_extractable": True, "chunk_count": 3, "page_count": 1}

    monkeypatch.setattr(paper_ingest, "register_paper", _fake_register)

    with TestClient(main.app) as client:
        resp = client.post(
            "/papers",
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


def test_register_paper_endpoint_400_on_invalid_pdf(monkeypatch):
    def _boom(pdf_path, **kw):
        raise fitz.FileDataError("cannot open broken document")

    monkeypatch.setattr(paper_ingest, "register_paper", _boom)

    with TestClient(main.app) as client:
        resp = client.post(
            "/papers", files={"file": ("bad.pdf", b"not a pdf at all", "application/pdf")}
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
        resp = client.get("/papers", params={"status": "recommended"})

    assert resp.status_code == 200
    assert resp.json() == {"papers": fake_rows}
    assert captured["status"] == "recommended"


def test_list_papers_no_filter_returns_all(monkeypatch):
    monkeypatch.setattr(paper_catalog, "list_papers", lambda *, status=None, **kw: [])

    with TestClient(main.app) as client:
        resp = client.get("/papers")

    assert resp.status_code == 200
    assert resp.json() == {"papers": []}


def test_list_papers_rejects_invalid_status():
    with TestClient(main.app) as client:
        resp = client.get("/papers", params={"status": "bogus"})

    assert resp.status_code == 422
