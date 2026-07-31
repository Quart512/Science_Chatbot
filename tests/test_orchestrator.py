"""
suggest_interest_node() / _find_duplicate() — orchestrator.py의 턴 종료 후 훅(08-07,
07-31 재설계). 당초 interrupt() 기반 독립 그래프였다가 평범한 노드+REST로 다시 짠 이유는
orchestrator.py 모듈 docstring 참고. invoke_with_fallback/interests.list_interests를
몽키패치해 순수 로직만 검증 — 실제 LLM·DB 호출 없음.
"""
from langchain_core.messages import HumanMessage

import interests
import orchestrator


def _fake_suggest_result(should_suggest, **draft_fields):
    return (
        orchestrator.InterestSuggestion(should_suggest=should_suggest, **draft_fields),
        "gemini", [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def _fake_dup_result(is_duplicate, duplicate_id=None):
    return (
        orchestrator.DuplicateCheck(is_duplicate=is_duplicate, duplicate_id=duplicate_id),
        "gemini", [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


DRAFT_FIELDS = dict(title="위상 물질", looking_for="기초 개념", already_known="", excluded_topics="")


# --- suggest_interest_node() ------------------------------------------------


def test_suggest_interest_skips_when_no_messages(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("메시지가 없으면 판정 자체를 하면 안 됨")
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", _boom)

    state = orchestrator.ParentState(question="q")
    result = orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "t1"}})

    assert result == {}


def test_suggest_interest_appends_comment_and_draft_when_true(monkeypatch):
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", lambda *a, **kw: _fake_suggest_result(True, **DRAFT_FIELDS))
    monkeypatch.setattr(interests, "list_interests", lambda **kw: [])  # 기존 관심사 없음 -> 중복 검사 스킵

    state = orchestrator.ParentState(
        question="q", comment="기존 코멘트", messages=[HumanMessage(content="위상 물질 계속 물어봄")]
    )
    result = orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "abc-123"}})

    assert result["comment"].startswith("기존 코멘트")  # 기존 코멘트를 지우지 않고 이어붙임
    assert "등록해볼까요" in result["comment"]


def test_suggest_interest_no_comment_change_when_false(monkeypatch):
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", lambda *a, **kw: _fake_suggest_result(False))

    state = orchestrator.ParentState(question="q", comment="원래 코멘트", messages=[HumanMessage(content="가벼운 질문")])
    result = orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "t1"}})

    assert "comment" not in result  # 안 건드림 — physics_qa_node가 이미 채운 comment가 그대로 유지됨


def test_suggest_interest_tracks_tokens_even_when_not_suggesting(monkeypatch):
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", lambda *a, **kw: _fake_suggest_result(False))

    state = orchestrator.ParentState(question="q", messages=[HumanMessage(content="질문")])
    result = orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "t1"}})

    assert result["tokens_used"]["total_tokens"] == 2


def test_suggest_interest_tracks_tokens_from_both_calls_when_duplicate_checked(monkeypatch):
    monkeypatch.setattr(interests, "list_interests", lambda **kw: [{"id": 1, "title": "x", "looking_for": "", "already_known": "", "excluded_topics": ""}])

    def _fake_invoke(model, messages, structured=None):
        if structured is orchestrator.InterestSuggestion:
            return _fake_suggest_result(True, **DRAFT_FIELDS)
        return _fake_dup_result(False)
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", _fake_invoke)

    state = orchestrator.ParentState(question="q", messages=[HumanMessage(content="질문")])
    result = orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "t1"}})

    assert result["tokens_used"]["total_tokens"] == 4  # 제안 판정(2) + 중복 검사(2)


def test_suggest_interest_continues_when_model_fails(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", _boom)

    state = orchestrator.ParentState(question="q", comment="원래 답변", messages=[HumanMessage(content="질문")])
    result = orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "t1"}})

    assert result == {}


def test_suggest_interest_skips_duplicate_check_when_no_existing_interests(monkeypatch):
    monkeypatch.setattr(interests, "list_interests", lambda **kw: [])
    calls = []
    def _fake_invoke(model, messages, structured=None):
        calls.append(structured)
        return _fake_suggest_result(True, **DRAFT_FIELDS)
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", _fake_invoke)

    state = orchestrator.ParentState(question="q", messages=[HumanMessage(content="질문")])
    orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "t1"}})

    assert calls == [orchestrator.InterestSuggestion]  # DuplicateCheck는 안 불림(기존 관심사가 없어서)


def test_suggest_interest_comment_mentions_duplicate_title(monkeypatch):
    monkeypatch.setattr(
        interests, "list_interests",
        lambda **kw: [{"id": 7, "title": "양자컴퓨팅", "looking_for": "", "already_known": "", "excluded_topics": ""}],
    )
    def _fake_invoke(model, messages, structured=None):
        if structured is orchestrator.InterestSuggestion:
            return _fake_suggest_result(True, **DRAFT_FIELDS)
        return _fake_dup_result(True, duplicate_id=7)
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", _fake_invoke)

    state = orchestrator.ParentState(question="q", messages=[HumanMessage(content="질문")])
    result = orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "t1"}})

    assert "양자컴퓨팅" in result["comment"]


# --- _find_duplicate() ------------------------------------------------------


def test_find_duplicate_returns_none_when_no_existing_interests(monkeypatch):
    monkeypatch.setattr(interests, "list_interests", lambda **kw: [])

    def _boom(*a, **kw):
        raise AssertionError("비교할 대상이 없으면 LLM을 부르면 안 됨")
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", _boom)

    dup, tokens = orchestrator._find_duplicate({"title": "x", "looking_for": "y"})
    assert dup is None
    assert tokens["total_tokens"] == 0


def test_find_duplicate_detects_match_and_uses_db_title_not_llm_title(monkeypatch):
    # duplicate_title을 LLM에게 새로 만들게 하지 않고 DB의 실제 값을 붙인다는 계약 확인
    monkeypatch.setattr(
        interests, "list_interests",
        lambda **kw: [{"id": 7, "title": "양자컴퓨팅", "looking_for": "오류 정정", "already_known": "", "excluded_topics": ""}],
    )
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", lambda *a, **kw: _fake_dup_result(True, duplicate_id=7))

    dup, tokens = orchestrator._find_duplicate({"title": "양자 오류 정정", "looking_for": "x"})

    assert dup == {"id": 7, "title": "양자컴퓨팅"}
    assert tokens["total_tokens"] == 2


def test_find_duplicate_returns_none_when_not_duplicate(monkeypatch):
    monkeypatch.setattr(
        interests, "list_interests",
        lambda **kw: [{"id": 1, "title": "무관한 주제", "looking_for": "", "already_known": "", "excluded_topics": ""}],
    )
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", lambda *a, **kw: _fake_dup_result(False))

    dup, tokens = orchestrator._find_duplicate({"title": "완전히 다른 주제", "looking_for": "x"})
    assert dup is None


def test_find_duplicate_ignores_hallucinated_id(monkeypatch):
    # LLM이 실재하지 않는 id를 대면 안전하게 "중복 아님"으로 취급
    monkeypatch.setattr(
        interests, "list_interests",
        lambda **kw: [{"id": 1, "title": "존재함", "looking_for": "", "already_known": "", "excluded_topics": ""}],
    )
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", lambda *a, **kw: _fake_dup_result(True, duplicate_id=999))

    dup, _ = orchestrator._find_duplicate({"title": "x", "looking_for": "y"})
    assert dup is None


def test_find_duplicate_gracefully_handles_model_failure(monkeypatch):
    monkeypatch.setattr(
        interests, "list_interests",
        lambda **kw: [{"id": 1, "title": "x", "looking_for": "", "already_known": "", "excluded_topics": ""}],
    )
    def _boom(*a, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", _boom)

    dup, tokens = orchestrator._find_duplicate({"title": "x", "looking_for": "y"})
    assert dup is None
    assert tokens["total_tokens"] == 0
