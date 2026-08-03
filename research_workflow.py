# 연구 워크플로우(⑥) — 가설 수립 → 실험 설계 → 실험 운영을 잇는 별도 그래프.
# 오케스트레이터(챗) 그래프와 State를 공유하지 않는다 — README "그래프 3개"(챗·연구
# 워크플로우·추천 파이프라인) 구조대로 독립된 최상위 그래프다. 며칠씩 걸리는 상태
# 있는 작업이라 체크포인터 영속화가 전제(main.py가 컴파일 시 연결, orchestrator.py와
# 같은 패턴 — 컴파일 전 graph 빌더만 여기서 export).
#
# 지금은 가설 수립 노드 하나뿐이다. 실험 설계(Plan-and-Execute)·실험 운영·안전
# 가드레일(interrupt_before HITL)·참고문헌 추천기 연동(references 누적)은 다음 단위
# (RoadMap "연구 워크플로우(⑥)" 참고) — 노드 하나마다 검증하고 다음으로 넘어간다.

import os

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import Literal

from models import invoke_with_fallback

TOKEN_KEYS = ("input_tokens", "output_tokens", "total_tokens")


def _add_tokens(current: dict, new: dict) -> dict:
    return {k: current.get(k, 0) + new.get(k, 0) for k in TOKEN_KEYS}


class WorkflowState(BaseModel):
    topic: str  # 사용자가 준 연구 주제·질문
    model: Literal["gemini", "claude", "Qwen-tuned"] = "gemini"
    disabled_models: list[str] = Field(default_factory=list)  # 모델 서킷 브레이커 — orchestrator.ParentState와 같은 패턴
    hypothesis: str = ""
    rationale: str = ""
    testable_prediction: str = ""
    tokens_used: dict = Field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})


HYPOTHESIS_SYSTEM_PROMPT = """주어진 연구 주제를 보고 검증 가능한 가설을 하나 세워라.
가설은 관찰이나 실험으로 참/거짓을 확인할 수 있는 구체적인 주장이어야 한다 —
"~일 것이다" 같은 모호한 진술이 아니라, 무엇을 측정하면 확인되는지가 분명해야 한다."""


class HypothesisOutput(BaseModel):
    statement: str = Field(description="검증 가능한 가설 문장")
    rationale: str = Field(description="이 가설을 세운 배경·근거")
    testable_prediction: str = Field(description="가설이 맞다면 실험·관찰에서 나타나야 할 구체적 결과")


def generate_hypothesis(state: WorkflowState) -> dict:
    messages = [
        SystemMessage(content=HYPOTHESIS_SYSTEM_PROMPT),
        HumanMessage(content=f"연구 주제: {state.topic}"),
    ]
    result, _, disabled_models, tokens_used = invoke_with_fallback(
        state.model, messages, structured=HypothesisOutput, disabled_models=state.disabled_models
    )
    return {
        "hypothesis": result.statement,
        "rationale": result.rationale,
        "testable_prediction": result.testable_prediction,
        "disabled_models": disabled_models,
        "tokens_used": _add_tokens(state.tokens_used, tokens_used),
    }


graph = StateGraph(WorkflowState)
graph.add_node("generate_hypothesis", generate_hypothesis)
graph.add_edge(START, "generate_hypothesis")
graph.add_edge("generate_hypothesis", END)

# 오케스트레이터의 checkpoints.sqlite와 별개 파일 — 두 그래프가 독립이라 State 스키마도
# 다르고, 체크포인트 보관 정책(연구 워크플로우는 며칠짜리 장기 상태)이 달라질 수 있어
# 처음부터 분리해둔다(orchestrator.py의 CHECKPOINT_DB_PATH와 같은 이유로 app.db와
# checkpoints.sqlite를 분리했던 논리 그대로).
CHECKPOINT_DB_PATH = "data/research_workflow_checkpoints.sqlite"


def ensure_checkpoint_dir() -> None:
    dirname = os.path.dirname(CHECKPOINT_DB_PATH)
    if dirname:
        os.makedirs(dirname, exist_ok=True)


if __name__ == "__main__":
    import asyncio

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async def _smoke_test():
        ensure_checkpoint_dir()
        async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as checkpointer:
            app = graph.compile(checkpointer=checkpointer)
            result = await app.ainvoke(
                {"topic": "그래핀의 전기전도도는 온도에 어떻게 의존하는가"},
                config={"configurable": {"thread_id": "test"}},
            )
            print("가설:", result["hypothesis"])
            print("근거:", result["rationale"])
            print("예측:", result["testable_prediction"])

    asyncio.run(_smoke_test())
