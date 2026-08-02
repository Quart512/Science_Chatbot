"""
draft_interest_from_messages() — orchestrator.py의 "관심사로 등록" 버튼(챗 사이드바)이
GET /interests/draft를 통해 호출하는 초안 생성 함수(08-02). 당초 있던 자동 제안 훅
(suggest_interest_node, 08-07~07-31)은 이 버튼 방식으로 교체되며 08-02에 삭제됐다 —
배경은 orchestrator.py의 draft_interest_from_messages 앞 주석 참고. invoke_with_fallback을
몽키패치해 순수 로직만 검증 — 실제 LLM 호출 없음.
"""
from langchain_core.messages import HumanMessage

import orchestrator


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
