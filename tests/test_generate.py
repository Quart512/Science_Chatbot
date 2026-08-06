# generate() — graph.py의 답변 생성 노드. invoke_with_fallback()이 모델 전부 실패로
# AllModelsFailedError를 던졌을 때(예: API 키가 하나도 없음) 스트림을 조용히 끊지 않고
# 원인을 답변 형태로 반환하는 계약만 검증한다(08-06, 포터블 번들 실기 테스트로 발견한
# 버그의 회귀 방지 — 실제 LLM 호출 없이 invoke_with_fallback을 몽키패치해서 확인).

from langchain_core.messages import AIMessage

import graph
from graph import generate
from models import AllModelsFailedError, model_map


def test_generate_returns_error_answer_when_all_models_fail(make_state, monkeypatch):
    # MissingAPIKeyError류(세션 내내 지속)라 전 모델이 진짜로 세션 차단감인 시나리오 —
    # disabled_models 정밀화(08-06) 이후에도 이 경우는 여전히 전체가 막혀야 정확하다.
    def _boom(*args, **kwargs):
        raise AllModelsFailedError(
            attempted=list(model_map.keys()),
            errors={m: "MissingAPIKeyError: ..." for m in model_map},
            disabled_models=list(model_map.keys()),
        )

    monkeypatch.setattr(graph, "invoke_with_fallback", _boom)
    state = make_state(question="테스트 질문")

    result = generate(state)

    assert result["fix_needed"] is False
    assert "API 키" in result["answer"] or "모델이 없습니다" in result["answer"]
    assert set(result["disabled_models"]) == set(model_map.keys())
    # route_after_generate가 state.messages[-1]에서 tool_calls를 읽으므로 마지막 메시지가
    # AIMessage(내용 있는)여야 한다 — None이면 다음 라운드에서 AttributeError로 다시 크래시.
    assert isinstance(result["messages"][-1], AIMessage)
    assert result["messages"][-1].content == result["answer"]


def test_generate_does_not_block_session_when_all_failures_are_request_scoped(make_state, monkeypatch):
    # disabled_models 정밀화(08-06) — 요청 자체 문제(길이 초과 등)로 전 모델이 같은
    # 이유로 실패했다면, AllModelsFailedError.disabled_models는 새로 추가된 게 없어
    # state.disabled_models 그대로다 — generate()가 그걸 그대로 반환해야
    # model_map 전체를 무조건 막던 예전 동작(회귀)이 아님을 보증한다.
    def _boom(*args, **kwargs):
        raise AllModelsFailedError(
            attempted=list(model_map.keys()), errors={}, disabled_models=[],
        )

    monkeypatch.setattr(graph, "invoke_with_fallback", _boom)
    state = make_state(question="테스트 질문")

    result = generate(state)

    assert result["disabled_models"] == []


def test_generate_error_path_does_not_add_tool_calls(make_state, monkeypatch):
    # route_after_generate가 tool_calls 유무로 run_tools/verify를 가르므로, 에러 답변에는
    # tool_calls가 없어야 verify로 곧장 가서 정상 종료된다(무한 tool 루프 방지).
    def _boom(*args, **kwargs):
        raise AllModelsFailedError(attempted=[], errors={}, disabled_models=[])

    monkeypatch.setattr(graph, "invoke_with_fallback", _boom)
    state = make_state(question="테스트 질문")

    result = generate(state)

    assert graph.route_after_generate(graph.State(question="x", messages=result["messages"])) == "verify"
