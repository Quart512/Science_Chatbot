"""
research_workflow.py — 연구 워크플로우(⑥) 1번째 노드 generate_hypothesis(). 그래프
노드를 맨 함수로 직접 부르는 이 저장소 관례(orchestrator.py 테스트와 동일) 그대로
invoke_with_fallback을 몽키패치해 순수 조립 로직만 검증 — 실제 LLM 호출 없음.
"""
import pytest

import research_workflow


def _fake_result(disabled_models=None, statement="가설", rationale="근거", prediction="예측"):
    return (
        research_workflow.HypothesisOutput(statement=statement, rationale=rationale, testable_prediction=prediction),
        "gemini", disabled_models or [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def test_generate_hypothesis_returns_structured_fields(monkeypatch):
    monkeypatch.setattr(
        research_workflow, "invoke_with_fallback",
        lambda *a, **kw: _fake_result(statement="온도가 오르면 저항이 커진다", rationale="금속의 일반적 특성", prediction="온도-저항 그래프가 우상향"),
    )

    state = research_workflow.WorkflowState(topic="금속의 전기저항은 온도에 어떻게 의존하는가")
    result = research_workflow.generate_hypothesis(state)

    assert result["hypothesis"] == "온도가 오르면 저항이 커진다"
    assert result["rationale"] == "금속의 일반적 특성"
    assert result["testable_prediction"] == "온도-저항 그래프가 우상향"


def test_generate_hypothesis_passes_disabled_models_through(monkeypatch):
    # physics_qa_node/draft_interest_from_messages와 같은 서킷 브레이커 패턴 —
    # 넘긴 disabled_models가 invoke_with_fallback에 그대로 전달되고, 갱신된 값이
    # 반환값에 실려야 한다.
    captured = {}
    def _fake_invoke(model, messages, structured=None, disabled_models=None):
        captured["disabled_models"] = disabled_models
        return _fake_result(disabled_models=disabled_models + ["gemini"])
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _fake_invoke)

    state = research_workflow.WorkflowState(topic="주제", disabled_models=["claude"])
    result = research_workflow.generate_hypothesis(state)

    assert captured["disabled_models"] == ["claude"]
    assert result["disabled_models"] == ["claude", "gemini"]


def test_generate_hypothesis_accumulates_tokens(monkeypatch):
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", lambda *a, **kw: _fake_result())

    state = research_workflow.WorkflowState(
        topic="주제", tokens_used={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    )
    result = research_workflow.generate_hypothesis(state)

    assert result["tokens_used"] == {"input_tokens": 11, "output_tokens": 6, "total_tokens": 17}


def test_generate_hypothesis_propagates_model_failure(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _boom)

    state = research_workflow.WorkflowState(topic="주제")
    with pytest.raises(RuntimeError):
        research_workflow.generate_hypothesis(state)
