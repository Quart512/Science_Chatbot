# generate() — graph.py의 답변 생성 노드. invoke_with_fallback()이 모델 전부 실패로
# RuntimeError를 던졌을 때(예: API 키가 하나도 없음) 스트림을 조용히 끊지 않고 원인을
# 답변 형태로 반환하는 계약만 검증한다(08-06, 포터블 번들 실기 테스트로 발견한 버그의
# 회귀 방지 — 실제 LLM 호출 없이 invoke_with_fallback을 몽키패치해서 확인).

from langchain_core.messages import AIMessage

import graph
from graph import generate
from models import model_map


def test_generate_returns_error_answer_when_all_models_fail(make_state, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("tried ['gemini', 'claude'] but all failed — gemini: MissingAPIKeyError: ...")

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


def test_generate_error_path_does_not_add_tool_calls(make_state, monkeypatch):
    # route_after_generate가 tool_calls 유무로 run_tools/verify를 가르므로, 에러 답변에는
    # tool_calls가 없어야 verify로 곧장 가서 정상 종료된다(무한 tool 루프 방지).
    monkeypatch.setattr(graph, "invoke_with_fallback", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("all failed")))
    state = make_state(question="테스트 질문")

    result = generate(state)

    assert graph.route_after_generate(graph.State(question="x", messages=result["messages"])) == "verify"
