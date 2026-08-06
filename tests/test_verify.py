# verify() — graph.py의 자체 검증 노드. 두 모델 다(1차: state.model 계열, 2차:
# generated_by) 실패했을 때 disabled_models를 어떻게 합치는지만 검증한다(08-06,
# "요청 자체 문제로 전 모델이 같은 이유로 실패해도 세션 내내 차단됐다" 버그의 회귀
# 방지 — 실제 LLM 호출 없이 invoke_with_fallback을 몽키패치해서 확인).

import graph
from graph import verify
from models import AllModelsFailedError


def test_verify_does_not_block_session_when_all_failures_are_request_scoped(make_state, monkeypatch):
    # 1차·2차 시도 둘 다 "새로 추가된 세션 차단 모델 없음"(disabled_models=state 그대로)을
    # 돌려주면, verify()가 예전처럼 model_map 전체를 막지 않고 원래 state.disabled_models를
    # 그대로 유지해야 한다.
    def _boom(*args, **kwargs):
        raise AllModelsFailedError(attempted=["gemini", "claude"], errors={}, disabled_models=["qwen-existing"])

    monkeypatch.setattr(graph, "invoke_with_fallback", _boom)
    state = make_state(
        question="테스트 질문", answer="어떤 답변", generated_by="claude",
        disabled_models=["qwen-existing"],
    )

    result = verify(state)

    assert result["fix_needed"] is False
    assert result["disabled_models"] == ["qwen-existing"]  # 새로 추가된 게 없음


def test_verify_combines_disabled_models_from_both_attempts(make_state, monkeypatch):
    # 1차 시도에서 "gemini"가, 2차 시도에서 "claude"가 각각 진짜 세션 차단감으로 판정됐다면
    # (서로 다른 원인으로) 최종 disabled_models는 둘 다 합쳐서 담아야 한다 — 어느 한쪽만
    # 반영하면 다음 턴에 그 모델이 조용히 다시 시도되는 회귀가 생긴다.
    calls = {"n": 0}

    def _boom(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise AllModelsFailedError(attempted=["gemini"], errors={}, disabled_models=["gemini"])
        raise AllModelsFailedError(attempted=["claude"], errors={}, disabled_models=["claude"])

    monkeypatch.setattr(graph, "invoke_with_fallback", _boom)
    state = make_state(question="테스트 질문", answer="어떤 답변", generated_by="claude", disabled_models=[])

    result = verify(state)

    assert set(result["disabled_models"]) == {"gemini", "claude"}
    assert result["comment"] == "검증을 수행하지 못해 결과를 확인 없이 반환합니다."
