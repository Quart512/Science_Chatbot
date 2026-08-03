# 연구 워크플로우(⑥) — 가설 수립 → 실험 설계 → 실험 운영을 잇는 별도 그래프.
# 오케스트레이터(챗) 그래프와 State를 공유하지 않는다 — README "그래프 3개"(챗·연구
# 워크플로우·추천 파이프라인) 구조대로 독립된 최상위 그래프다. 며칠씩 걸리는 상태
# 있는 작업이라 체크포인터 영속화가 전제(main.py가 컴파일 시 연결, orchestrator.py와
# 같은 패턴 — 컴파일 전 graph 빌더만 여기서 export).
#
# 가설 수립 다음 노드로 참고문헌 추천기(reference_recommender)를 연동했다 — 실험
# 설계(Plan-and-Execute)·실험 운영·안전 가드레일(interrupt_before HITL)은 다음 단위
# (RoadMap "연구 워크플로우(⑥)" 참고) — 노드 하나마다 검증하고 다음으로 넘어간다.

import os

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import Literal

from models import invoke_with_fallback
import reference_recommender

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
    # 워크플로우가 끌고 다니는 누적 참고문헌 목록(README "참고문헌은 워크플로우가 끌고
    # 다니는 누적 산출물" 참고) — 각 항목: {"paper_id", "title", "source": "owned"|
    # "external", "reasoning", "added_by_stage"}. 뒤에 올 실험 설계·운영·논문 작성
    # 단계도 각자 이 목록에 이어붙인다(paper_id로 중복 방지, 처음 추가한 단계만 표시).
    references: list[dict] = Field(default_factory=list)
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


def find_hypothesis_references(state: WorkflowState) -> dict:
    """방금 나온 가설 문장으로 참고문헌 추천기를 호출해 워크플로우 공유 references에
    누적한다. 이미 목록에 있는 paper_id는 건너뛴다(다른 단계가 먼저 찾았을 수 있음 —
    처음 추가한 단계 표시를 그대로 둔다).

    실패(모델 소진 등)는 이 단계만 건너뛴다 — 가설 자체는 이미 만들어졌으므로 참고문헌
    하나 못 찾았다고 워크플로우 전체를 실패시킬 이유가 없다(관심사 자동 제안 훅이
    쓰던 것과 같은 논리, 08-02에 삭제됐지만 "부가 기능 실패가 핵심 결과를 막지 않는다"
    원칙은 유효).
    """
    try:
        found = reference_recommender.recommend_references(state.hypothesis)
    except RuntimeError as e:
        print(f"참고문헌 추천 실패(이 단계는 건너뜀): {type(e).__name__}: {e}")
        return {}

    existing_ids = {r["paper_id"] for r in state.references}
    new_entries = [
        {**r, "added_by_stage": "hypothesis"} for r in found if r["paper_id"] not in existing_ids
    ]
    return {"references": state.references + new_entries}


graph = StateGraph(WorkflowState)
graph.add_node("generate_hypothesis", generate_hypothesis)
graph.add_node("find_hypothesis_references", find_hypothesis_references)
graph.add_edge(START, "generate_hypothesis")
graph.add_edge("generate_hypothesis", "find_hypothesis_references")
graph.add_edge("find_hypothesis_references", END)

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
            print("참고문헌:", [r["title"] for r in result["references"]])

    asyncio.run(_smoke_test())
