"""
interest_writer.py — 관심사 문서 작성기(독립 그래프)의 톨게이트 테스트. draft/dup_check/save는
직접 호출해 순수 로직만 검증(LLM·interests.py는 몽키패치). confirm()은 interrupt()가
LangGraph 실행 컨텍스트(get_config())를 요구해서 직접 호출이 안 되므로, 실제 그래프를
InMemorySaver(랭그래프 표준 인메모리 체크포인터, aget/aput 등 async 메서드를 전부 지원 —
동기 SqliteSaver와 달리 :memory: 수준으로 빠르고 astream()에서도 그대로 쓸 수 있음)로
컴파일해 진짜 실행한다. asyncio.run()으로 감싸는 이유: 이 프로젝트엔 pytest-asyncio가
없어서(새 의존성 피함) 각 테스트가 자기 이벤트 루프를 직접 돌린다.
"""
import asyncio

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import interest_writer
import interests
import orchestrator


def _fake_extraction_result(obj):
    return (obj, "gemini", [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})


# --- draft() ----------------------------------------------------------


def test_draft_skips_llm_when_manual_input_already_provided(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("title이 이미 채워져 있으면 LLM을 부르면 안 됨(수동 입력 경로)")
    monkeypatch.setattr(interest_writer, "invoke_with_fallback", _boom)

    state = interest_writer.InterestWriterState(title="이미 채워진 제목")
    result = asyncio.run(interest_writer.draft(state, {"configurable": {}}))

    assert result == {}


def test_draft_returns_empty_when_no_seed_thread(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("seed_thread_id가 없으면 LLM을 부르면 안 됨")
    monkeypatch.setattr(interest_writer, "invoke_with_fallback", _boom)

    state = interest_writer.InterestWriterState()
    result = asyncio.run(interest_writer.draft(state, {"configurable": {}}))

    assert result == {}


def test_draft_fills_template_from_seeded_conversation(monkeypatch):
    captured = {}
    def _fake_invoke(model, messages, structured=None):
        captured["history_text"] = messages[-1].content
        extraction = interest_writer.InterestDraft(
            title="위상 물질", looking_for="기초 개념", already_known="", excluded_topics=""
        )
        return _fake_extraction_result(extraction)
    monkeypatch.setattr(interest_writer, "invoke_with_fallback", _fake_invoke)

    async def _run():
        # orchestrator.graph를 InMemorySaver로 컴파일해 "이전 대화"를 직접 주입한다 —
        # 실제 물리 QA를 돌리지 않고도(API 키 불필요) draft()가 그 thread_id를 읽는지 확인.
        cp = InMemorySaver()
        qa_app = orchestrator.graph.compile(checkpointer=cp)
        config = {"configurable": {"thread_id": "seed-1"}}
        await qa_app.aupdate_state(config, {
            # question은 ParentState 필수 필드라 aget_state()가 다음 태스크를 준비할 때
            # 검증에 걸린다 — draft()는 messages만 쓰지만 값은 채워둬야 함
            "question": "위상 물질에 관심 있어",
            "messages": [HumanMessage(content="위상 물질에 관심 있어"), AIMessage(content="위상 물질은...")],
        })

        state = interest_writer.InterestWriterState(seed_thread_id="seed-1")
        return await interest_writer.draft(state, {"configurable": {"qa_checkpointer": cp}})

    result = asyncio.run(_run())

    assert result["title"] == "위상 물질"
    assert "위상 물질에 관심 있어" in captured["history_text"]


def test_draft_returns_empty_when_seeded_thread_has_no_messages(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("빈 대화 이력이면 LLM을 부르면 안 됨")
    monkeypatch.setattr(interest_writer, "invoke_with_fallback", _boom)

    async def _run():
        cp = InMemorySaver()
        state = interest_writer.InterestWriterState(seed_thread_id="never-existed")
        return await interest_writer.draft(state, {"configurable": {"qa_checkpointer": cp}})

    result = asyncio.run(_run())
    assert result == {}


# --- dup_check() --------------------------------------------------------


def test_dup_check_skips_llm_when_no_existing_interests(monkeypatch):
    monkeypatch.setattr(interests, "list_interests", lambda **kw: [])

    def _boom(*a, **kw):
        raise AssertionError("기존 관심사가 없으면 비교할 대상이 없어 LLM을 부르면 안 됨")
    monkeypatch.setattr(interest_writer, "invoke_with_fallback", _boom)

    state = interest_writer.InterestWriterState(title="새 관심사")
    assert interest_writer.dup_check(state) == {}


def test_dup_check_detects_duplicate(monkeypatch):
    monkeypatch.setattr(
        interests, "list_interests",
        lambda **kw: [{"id": 7, "title": "양자컴퓨팅", "looking_for": "오류 정정", "already_known": "", "excluded_topics": ""}],
    )
    monkeypatch.setattr(
        interest_writer, "invoke_with_fallback",
        lambda model, messages, structured=None: _fake_extraction_result(
            interest_writer.DuplicateCheck(is_duplicate=True, duplicate_id=7, reasoning="같은 주제")
        ),
    )

    state = interest_writer.InterestWriterState(title="양자 오류 정정")
    result = interest_writer.dup_check(state)

    assert result == {"duplicate_id": 7, "duplicate_reasoning": "같은 주제"}


def test_dup_check_no_duplicate_found(monkeypatch):
    monkeypatch.setattr(
        interests, "list_interests",
        lambda **kw: [{"id": 1, "title": "무관한 주제", "looking_for": "", "already_known": "", "excluded_topics": ""}],
    )
    monkeypatch.setattr(
        interest_writer, "invoke_with_fallback",
        lambda model, messages, structured=None: _fake_extraction_result(
            interest_writer.DuplicateCheck(is_duplicate=False)
        ),
    )

    state = interest_writer.InterestWriterState(title="완전히 다른 주제")
    assert interest_writer.dup_check(state) == {}


# --- save() ---------------------------------------------------------------


def test_save_creates_new_interest_on_create_decision(monkeypatch):
    captured = {}
    def _fake_create(title, looking_for="", already_known="", excluded_topics="", **kw):
        captured.update(title=title, looking_for=looking_for)
        return 42
    monkeypatch.setattr(interests, "create_interest", _fake_create)

    state = interest_writer.InterestWriterState(decision="create", title="제목", looking_for="찾는것")
    result = interest_writer.save(state)

    assert result == {"saved_interest_id": 42}
    assert captured == {"title": "제목", "looking_for": "찾는것"}


def test_save_updates_existing_on_update_existing_decision(monkeypatch):
    captured = {}
    def _fake_update(interest_id, **fields):
        captured["id"] = interest_id
        captured["fields"] = fields
        return True
    monkeypatch.setattr(interests, "update_interest", _fake_update)

    state = interest_writer.InterestWriterState(
        decision="update_existing", duplicate_id=7, title="수정된 제목",
        looking_for="", already_known="", excluded_topics="",
    )
    result = interest_writer.save(state)

    assert result == {"saved_interest_id": 7}
    assert captured["id"] == 7
    assert captured["fields"]["title"] == "수정된 제목"


def test_save_does_nothing_on_cancel(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("cancel이면 DB에 쓰면 안 됨")
    monkeypatch.setattr(interests, "create_interest", _boom)
    monkeypatch.setattr(interests, "update_interest", _boom)

    state = interest_writer.InterestWriterState(decision="cancel", title="제목")
    assert interest_writer.save(state) == {}


# --- route_after_confirm() -------------------------------------------------


def test_route_after_confirm_create_goes_to_save():
    state = interest_writer.InterestWriterState(decision="create")
    assert interest_writer.route_after_confirm(state) == "save"


def test_route_after_confirm_update_existing_goes_to_save():
    state = interest_writer.InterestWriterState(decision="update_existing")
    assert interest_writer.route_after_confirm(state) == "save"


def test_route_after_confirm_cancel_stops():
    state = interest_writer.InterestWriterState(decision="cancel")
    assert interest_writer.route_after_confirm(state) == "cancelled"


# --- 전체 그래프: interrupt/resume 메커니즘 --------------------------------
# InMemorySaver를 쓰는 이유: interrupt/resume "의미"는 체크포인터 구현체와 무관하다
# (그게 체크포인터 추상화의 핵심) — 실제 디스크 영속성은 6-4에서 AsyncSqliteSaver로 이미
# 검증했으므로, 여기서는 이 그래프의 노드 구조가 그 의미를 올바르게 쓰는지만 빠르게 본다.


def test_graph_pauses_at_confirm_and_surfaces_draft(monkeypatch):
    monkeypatch.setattr(interests, "list_interests", lambda **kw: [])

    async def _run():
        cp = InMemorySaver()
        app = interest_writer.graph.compile(checkpointer=cp)
        config = {"configurable": {"thread_id": "t-pause", "qa_checkpointer": cp}}
        return await app.ainvoke({"title": "제목", "looking_for": "찾는것"}, config)

    result = asyncio.run(_run())

    assert "__interrupt__" in result
    payload = result["__interrupt__"][0].value
    assert payload["draft"]["title"] == "제목"
    assert payload["duplicate_id"] is None


def test_graph_does_not_rerun_dup_check_llm_call_after_resume(monkeypatch):
    # 07-31 설계 논의에서 확인한 langgraph 제약의 회귀 방지: confirm 노드는 재개 시
    # 처음부터 재실행되지만, 그 앞의 draft/dup_check는 재실행되면 안 된다(이미 정상
    # 반환해 체크포인트에 커밋됐으므로). dup_check가 부르는 invoke_with_fallback 호출
    # 횟수로 이걸 증명한다 — 재실행됐다면 2번 찍혀야 하는데 1번이어야 정상.
    calls = []
    def _fake_invoke(model, messages, structured=None):
        calls.append(1)
        return _fake_extraction_result(interest_writer.DuplicateCheck(is_duplicate=False))
    monkeypatch.setattr(interest_writer, "invoke_with_fallback", _fake_invoke)
    monkeypatch.setattr(
        interests, "list_interests",
        lambda **kw: [{"id": 1, "title": "기존 관심사", "looking_for": "x", "already_known": "", "excluded_topics": ""}],
    )
    saved = {}
    monkeypatch.setattr(interests, "create_interest", lambda *a, **kw: (saved.setdefault("called", True), 42)[1])

    async def _run():
        cp = InMemorySaver()
        app = interest_writer.graph.compile(checkpointer=cp)
        config = {"configurable": {"thread_id": "t-resume", "qa_checkpointer": cp}}

        paused = await app.ainvoke({"title": "새 제목", "looking_for": "찾는것"}, config)
        assert "__interrupt__" in paused
        assert len(calls) == 1  # dup_check가 1차 실행에서 정확히 한 번만 LLM 호출

        resumed = await app.ainvoke(Command(resume={"action": "create"}), config)
        return resumed

    resumed = asyncio.run(_run())

    assert len(calls) == 1  # 재개 후에도 여전히 1번 — dup_check가 재실행되지 않았다는 증거
    assert resumed["saved_interest_id"] == 42
    assert saved.get("called") is True


def test_graph_resume_with_cancel_does_not_save(monkeypatch):
    monkeypatch.setattr(interests, "list_interests", lambda **kw: [])

    def _boom(*a, **kw):
        raise AssertionError("cancel로 재개하면 저장하면 안 됨")
    monkeypatch.setattr(interests, "create_interest", _boom)
    monkeypatch.setattr(interests, "update_interest", _boom)

    async def _run():
        cp = InMemorySaver()
        app = interest_writer.graph.compile(checkpointer=cp)
        config = {"configurable": {"thread_id": "t-cancel", "qa_checkpointer": cp}}

        await app.ainvoke({"title": "제목", "looking_for": "찾는것"}, config)
        return await app.ainvoke(Command(resume={"action": "cancel"}), config)

    result = asyncio.run(_run())
    assert result.get("saved_interest_id") is None


def test_graph_resume_can_apply_edits_before_save(monkeypatch):
    # confirm 노드가 resume 값의 edits를 반영해야 한다 — 사용자가 확인 화면에서
    # 필드를 고쳐서 확정하는 경우(모듈 docstring "resume 값 형태" 참고)
    monkeypatch.setattr(interests, "list_interests", lambda **kw: [])
    captured = {}
    monkeypatch.setattr(
        interests, "create_interest",
        lambda title, looking_for="", already_known="", excluded_topics="", **kw: (
            captured.update(title=title, looking_for=looking_for), 99
        )[1],
    )

    async def _run():
        cp = InMemorySaver()
        app = interest_writer.graph.compile(checkpointer=cp)
        config = {"configurable": {"thread_id": "t-edit", "qa_checkpointer": cp}}

        await app.ainvoke({"title": "원래 제목", "looking_for": "원래 내용"}, config)
        return await app.ainvoke(
            Command(resume={"action": "create", "edits": {"title": "고친 제목"}}), config
        )

    asyncio.run(_run())

    assert captured["title"] == "고친 제목"
    assert captured["looking_for"] == "원래 내용"  # 안 고친 필드는 그대로
