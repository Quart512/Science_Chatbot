"""
draft_interest_from_messages() — orchestrator.py의 "관심사로 등록" 버튼(챗 사이드바)이
GET /interests/draft를 통해 호출하는 초안 생성 함수(08-02). 당초 있던 자동 제안 훅
(suggest_interest_node, 08-07~07-31)은 이 버튼 방식으로 교체되며 08-02에 삭제됐다 —
배경은 orchestrator.py의 draft_interest_from_messages 앞 주석 참고. invoke_with_fallback을
몽키패치해 순수 로직만 검증 — 실제 LLM 호출 없음.

_trim_history() — 08-13 멀티턴 메시지 트리밍의 순수 로직(오래된 [Human, AI] 쌍부터
문자 예산 초과분을 잘라냄). MESSAGE_HISTORY_BUDGET_CHARS를 몽키패치해 예산을 테스트마다
통제 가능한 작은 값으로 고정.
"""
from langchain_core.messages import AIMessage, HumanMessage

import orchestrator


def _turn(n: int) -> list:
    # 매 턴 [Human, AI] 2개, 각각 정확히 10자(ASCII) — 예산 계산을 손으로 검증하기 쉽게
    return [HumanMessage(content=f"h{n:09d}"), AIMessage(content=f"a{n:09d}")]


DRAFT_FIELDS = dict(title="위상 물질", looking_for="기초 개념", already_known="", excluded_topics="")


def _fake_draft_result(disabled_models=None, **draft_fields):
    return (
        orchestrator.InterestDraft(**draft_fields),
        "gemini", disabled_models or [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def test_draft_interest_returns_empty_when_no_messages():
    draft, tokens, disabled_models = orchestrator.draft_interest_from_messages([])
    assert draft == {"title": "", "looking_for": "", "already_known": "", "excluded_topics": ""}
    assert tokens == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    assert disabled_models == []


def test_draft_interest_returns_fields_from_llm(monkeypatch):
    calls = []
    def _fake_invoke(model, messages, structured=None, disabled_models=None):
        calls.append(structured)
        return _fake_draft_result(**DRAFT_FIELDS)
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", _fake_invoke)

    draft, tokens, _ = orchestrator.draft_interest_from_messages([HumanMessage(content="위상 물질 재밌다")])

    assert draft == DRAFT_FIELDS
    assert tokens["total_tokens"] == 2
    # should_suggest 판정 없이 곧장 InterestDraft로 물어봄
    assert calls == [orchestrator.InterestDraft]


def test_draft_interest_continues_when_model_fails(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", _boom)

    draft, tokens, disabled_models = orchestrator.draft_interest_from_messages([HumanMessage(content="질문")])

    assert draft == {"title": "", "looking_for": "", "already_known": "", "excluded_topics": ""}
    assert tokens["total_tokens"] == 0
    assert disabled_models == []


def test_draft_interest_passes_disabled_models_through(monkeypatch):
    # physics_qa_node와 같은 서킷 브레이커 — 호출자가 넘긴 disabled_models를 invoke_with_fallback에
    # 그대로 전달하고, 갱신된 값을 돌려받아 반환값에 실어야 한다(main.py가 체크포인트에 다시 씀).
    captured = {}
    def _fake_invoke(model, messages, structured=None, disabled_models=None):
        captured["disabled_models"] = disabled_models
        return _fake_draft_result(disabled_models=disabled_models + ["gemini"], **DRAFT_FIELDS)
    monkeypatch.setattr(orchestrator, "invoke_with_fallback", _fake_invoke)

    _, _, updated = orchestrator.draft_interest_from_messages(
        [HumanMessage(content="질문")], disabled_models=["claude"]
    )

    assert captured["disabled_models"] == ["claude"]
    assert updated == ["claude", "gemini"]


# --- _trim_history() (08-13, 멀티턴 메시지 트리밍) ---------------------------


def test_trim_history_no_trim_when_under_budget(monkeypatch):
    monkeypatch.setattr(orchestrator, "MESSAGE_HISTORY_BUDGET_CHARS", {"gemini": 1000})
    messages = _turn(1) + _turn(2)

    kept, removed = orchestrator._trim_history(messages, "gemini")

    assert kept == messages
    assert removed == []


def test_trim_history_skips_short_history_regardless_of_budget(monkeypatch):
    # 메시지가 1턴(2개) 이하면 예산이 아무리 작아도 자를 게 없음(최소 마지막 턴은 항상 남김)
    monkeypatch.setattr(orchestrator, "MESSAGE_HISTORY_BUDGET_CHARS", {"gemini": 1})
    messages = _turn(1)

    kept, removed = orchestrator._trim_history(messages, "gemini")

    assert kept == messages
    assert removed == []


def test_trim_history_removes_oldest_turn_first(monkeypatch):
    # 턴 하나가 20자(Human 10 + AI 10) — 예산 45자면 2턴(40자)은 들어가고 3턴째(60자)부터 넘침
    monkeypatch.setattr(orchestrator, "MESSAGE_HISTORY_BUDGET_CHARS", {"gemini": 45})
    turn1, turn2, turn3 = _turn(1), _turn(2), _turn(3)
    messages = turn1 + turn2 + turn3

    kept, removed = orchestrator._trim_history(messages, "gemini")

    assert removed == turn1  # 가장 오래된 턴만 잘림
    assert kept == turn2 + turn3


def test_trim_history_always_keeps_last_turn_even_over_budget(monkeypatch):
    # 마지막 턴 하나만으로도 예산(1자)을 넘지만, 직전 맥락 없인 답할 수 없으니 항상 남긴다
    monkeypatch.setattr(orchestrator, "MESSAGE_HISTORY_BUDGET_CHARS", {"gemini": 1})
    turn1, turn2 = _turn(1), _turn(2)
    messages = turn1 + turn2

    kept, removed = orchestrator._trim_history(messages, "gemini")

    assert kept == turn2
    assert removed == turn1


def test_trim_history_skips_when_model_has_no_budget(monkeypatch):
    monkeypatch.setattr(orchestrator, "MESSAGE_HISTORY_BUDGET_CHARS", {})  # gemini 항목 없음
    messages = _turn(1) + _turn(2) + _turn(3)

    kept, removed = orchestrator._trim_history(messages, "gemini")

    assert kept == messages
    assert removed == []
