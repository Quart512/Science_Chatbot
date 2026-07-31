"""
suggest_interest_node() — orchestrator.py의 턴 종료 후 훅(08-07). 물리 QA가 아니라
부모가 소유하는 이유·설계는 orchestrator.py 모듈 docstring 참고. invoke_with_fallback을
몽키패치해 순수 로직만 검증 — 실제 LLM 호출 없음.
"""
from langchain_core.messages import HumanMessage

import orchestrator


def _fake_result(should_suggest):
    return (
        orchestrator.InterestSuggestion(should_suggest=should_suggest),
        "gemini",
        [],
        {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def test_suggest_interest_skips_when_no_messages(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("메시지가 없으면 판정 자체를 하면 안 됨")
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", _boom)

    state = orchestrator.ParentState(question="q")
    result = orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "t1"}})

    assert result == {}


def test_suggest_interest_appends_comment_with_thread_id_when_true(monkeypatch):
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", lambda *a, **kw: _fake_result(True))

    state = orchestrator.ParentState(
        question="q", comment="기존 코멘트", messages=[HumanMessage(content="위상 물질 계속 물어봄")]
    )
    result = orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "abc-123"}})

    assert result["comment"].startswith("기존 코멘트")  # 기존 코멘트를 지우지 않고 이어붙임
    assert "abc-123" in result["comment"]


def test_suggest_interest_no_comment_change_when_false(monkeypatch):
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", lambda *a, **kw: _fake_result(False))

    state = orchestrator.ParentState(question="q", comment="원래 코멘트", messages=[HumanMessage(content="가벼운 질문")])
    result = orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "t1"}})

    assert "comment" not in result  # 안 건드림 — physics_qa_node가 이미 채운 comment가 그대로 유지됨


def test_suggest_interest_tracks_tokens_even_when_not_suggesting(monkeypatch):
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", lambda *a, **kw: _fake_result(False))

    state = orchestrator.ParentState(question="q", messages=[HumanMessage(content="질문")])
    result = orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "t1"}})

    assert result["tokens_used"]["total_tokens"] == 2  # 제안 안 해도 판정에 쓴 토큰은 누적


def test_suggest_interest_continues_when_model_fails(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", _boom)

    state = orchestrator.ParentState(question="q", comment="원래 답변", messages=[HumanMessage(content="질문")])
    result = orchestrator.suggest_interest_node(state, {"configurable": {"thread_id": "t1"}})

    # 판정 실패해도 조용히 빈 업데이트만 반환 — 턴 전체가 죽지 않음(원래 answer/comment는
    # physics_qa_node가 이미 반환한 값이 그대로 살아있음, 여기선 그걸 건드리지 않는지만 확인)
    assert result == {}
