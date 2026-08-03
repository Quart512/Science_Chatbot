# 연구 워크플로우(⑥) — 가설 수립 → 실험 설계 → 실험 운영을 잇는 별도 그래프.
# 오케스트레이터(챗) 그래프와 State를 공유하지 않는다 — README "그래프 3개"(챗·연구
# 워크플로우·추천 파이프라인) 구조대로 독립된 최상위 그래프다. 며칠씩 걸리는 상태
# 있는 작업이라 체크포인터 영속화가 전제(main.py가 컴파일 시 연결, orchestrator.py와
# 같은 패턴 — 컴파일 전 graph 빌더만 여기서 export).
#
# 가설 수립 → 실험 설계 → 실험 운영까지 연결됐다. 안전 가드레일(interrupt_before HITL)은
# 다음 단위(RoadMap "연구 워크플로우(⑥)" 참고) — 노드 하나마다 검증하고 다음으로 넘어간다.
#
# 단계 전환은 START의 조건부 엣지(route_by_stage)가 state.stage를 보고 담당한다(08-02,
# 사용자 제안 — 처음엔 aget_state로 읽어 파이썬 함수를 직접 부르고 aupdate_state로
# 쓰는 방식(advance_to_design)으로 짰다가, "그냥 START에서 라우팅하면 안 되냐"는 지적을
# 받고 실제로 되는지 확인한 뒤(별도 토이 그래프로 재현) 이 방식으로 교체했다). 사람이
# "다음 단계로" 트리거하면 호출부가 `ainvoke({"stage": "design", ...새 입력}, config)`
# **한 번만** 부르면 된다 — stage 갱신과 새 입력(예: 실험 결과)이 같은 invoke 호출
# 안에서 함께 반영되는 것도 실제로 확인했다(별도 aupdate_state 호출 불필요). 라우터가
# 알아서 해당 단계 노드로 보내고, 그 노드는 체크포인트에 이미 있는 이전 단계 값을
# 그대로 본다. 이 방식이 더 나은 이유: 모든 단계가 똑같이 그래프 엔진(스트리밍·트레이싱
# 포함)을 타서 1단계만 특별 취급하던 비일관성이 없고, 단계가 늘어도 새 글루 함수 없이
# 라우팅 분기+엣지만 추가하면 된다 — "재설계 필요" 판정이 나와도 사람이 stage를 다시
# "design"으로 돌리기만 하면 되므로 별도 되돌아가는 엣지도 필요 없다.
#
# 실험 설계는 README상 "Plan-and-Execute"가 핵심 기법으로 적혀 있지만(계획자가 단계를
# 짜고 실행자가 tool 호출을 섞어가며 수행, 필요시 재계획하는 멀티스텝 에이전트 패턴),
# 여기선 그 분리를 안 한다(08-02, 사용자 판단) — Plan-and-Execute가 원래 막으려는 건
# "설계 없이 바로 행동"인데, 이 단계의 산출물 자체가 설계 문서라 "실행"이 따로 없다
# (행동은 다음 단계인 실험 운영에서 일어남). 그래서 LLM 호출 한 번으로 가설+보유
# 장비 목록(equipment.py, 목록이 짧아 프롬프트에 통째로 넣는 게 RoadMap이 이미 정한
# 방식)을 보고 구조화된 설계를 바로 뽑는다.

import os

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import Callable, Literal

from models import invoke_with_fallback
import equipment
import reference_recommender

TOKEN_KEYS = ("input_tokens", "output_tokens", "total_tokens")


def _add_tokens(current: dict, new: dict) -> dict:
    return {k: current.get(k, 0) + new.get(k, 0) for k in TOKEN_KEYS}


class WorkflowState(BaseModel):
    topic: str  # 사용자가 준 연구 주제·질문
    # 지금 어느 단계인지 — START의 조건부 엣지가 이 값으로 라우팅한다. 기본값이
    # "hypothesis"라 처음 만드는 thread는 자동으로 가설 단계부터 시작하고, 사용자가
    # "다음 단계로"를 누르면 호출부가 이 필드(+필요하면 새 입력)를 담아 다시 invoke하면 된다.
    stage: Literal["hypothesis", "design", "operation"] = "hypothesis"
    model: Literal["gemini", "claude", "Qwen-tuned"] = "gemini"
    disabled_models: list[str] = Field(default_factory=list)  # 모델 서킷 브레이커 — orchestrator.ParentState와 같은 패턴
    hypothesis: str = ""
    rationale: str = ""
    testable_prediction: str = ""
    independent_variable: str = ""
    dependent_variable: str = ""
    controlled_variables: str = ""
    equipment_needed: str = ""
    procedure: str = ""
    # 실험 운영 단계 — experiment_results는 사용자가 실제로 실험을 하고 와서 입력하는
    # 값이라 LLM이 만들지 않는다(가설/설계와 성격이 다름). analysis/needs_redesign은
    # 그 결과를 testable_prediction과 비교해 LLM이 뽑는다.
    experiment_results: str = ""
    analysis: str = ""
    needs_redesign: bool = False
    # 워크플로우가 끌고 다니는 누적 참고문헌 목록(README "참고문헌은 워크플로우가 끌고
    # 다니는 누적 산출물" 참고) — 각 항목: {"paper_id", "title", "source": "owned"|
    # "external", "reasoning", "added_by_stage"}. 뒤에 올 실험 설계·운영·논문 작성
    # 단계도 각자 이 목록에 이어붙인다(paper_id로 중복 방지, 처음 추가한 단계만 표시).
    references: list[dict] = Field(default_factory=list)
    # 사람에게 보여줄 결정론적 안내 문구(graph.py의 comment와 같은 채널 — LLM이 아니라
    # 코드가 채움, 매번 덮어씀). "이미 증명된 이론·이미 한 실험인지"를 LLM이 판정하는
    # 대신, 사람이 직접 참고문헌(이미 스크리닝 근거·연관성이 붙어 있음)을 보고 템플릿을
    # 고치거나 재생성하도록 안내만 한다(08-02, 사용자 판단 — "판정 대신 추출/신호"
    # 원칙과 같은 결).
    comment: str = ""
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


def _make_reference_node(get_text: Callable[["WorkflowState"], str], stage_name: str):
    """참고문헌 추천 노드를 찍어내는 클로저 팩토리 — tool.py의 make_search_tool과 같은
    패턴(그쪽은 site별 검색 tool, 여긴 단계별 참고문헌 노드). 스테이지마다 하는 일은
    "자기 산출물 텍스트로 검색해서 공유 references에 누적"으로 완전히 같고, 다른 건
    어느 필드(들)를 검색어로 쓰는지와 added_by_stage 값뿐이라 그때그때 복붙하는 대신
    get_text(state)로 위임한다.

    실패(모델 소진 등)는 이 단계만 건너뛴다 — 앞 단계 산출물은 이미 나왔으므로
    참고문헌 하나 못 찾았다고 워크플로우 전체를 실패시킬 이유가 없다(삭제된 관심사
    자동 제안 훅이 쓰던 것과 같은 논리: 부가 기능 실패가 핵심 결과를 막지 않는다).

    "이미 증명된 이론·이미 한 실험인지"는 LLM이 판정하지 않는다 — 찾은 참고문헌(이미
    screen_candidate의 연관성 근거가 붙어 있음)을 사람이 직접 읽고 템플릿을 고치거나
    재생성할지 판단하도록 comment로 안내만 한다.
    """
    def node(state: WorkflowState) -> dict:
        try:
            found = reference_recommender.recommend_references(get_text(state))
        except RuntimeError as e:
            print(f"참고문헌 추천 실패(이 단계는 건너뜀): {type(e).__name__}: {e}")
            return {"comment": "참고문헌 추천에 실패했습니다 — 직접 템플릿을 검토해주세요."}

        existing_ids = {r["paper_id"] for r in state.references}
        new_entries = [
            {**r, "added_by_stage": stage_name} for r in found if r["paper_id"] not in existing_ids
        ]

        if new_entries:
            comment = (
                "참고논문을 확인해서 선행 연구된 내용이 있는지 확인하고 템플릿을 채우거나 "
                "수정해주세요. 참고문헌이 부족하다면 재생성을 눌러주세요."
            )
        else:
            comment = "참고문헌을 찾지 못했습니다 — 재생성을 눌러 다시 시도하거나 직접 템플릿을 채워주세요."

        return {"references": state.references + new_entries, "comment": comment}

    return node


find_hypothesis_references = _make_reference_node(lambda s: s.hypothesis, "hypothesis")
find_design_references = _make_reference_node(lambda s: s.procedure, "design")


EXPERIMENT_DESIGN_SYSTEM_PROMPT = """주어진 가설을 검증할 실험을 설계해라. 독립변수·
종속변수·통제변수를 명확히 구분하고, 실험 절차를 구체적인 순서로 적어라. 필요한
장비는 아래 "보유 장비 목록"에 있는 것을 최우선으로 활용하고, 목록에 없는 장비가
꼭 필요하면 그것도 적되 목록에 없다는 걸 명시해라."""


class ExperimentDesign(BaseModel):
    independent_variable: str = Field(description="조작하는 변수 — 무엇을 바꿔가며 관찰하는지")
    dependent_variable: str = Field(description="측정하는 변수 — 무엇을 재는지")
    controlled_variables: str = Field(description="일정하게 유지할 변수들")
    equipment_needed: str = Field(description="필요한 장비 — 보유 장비 목록 활용, 없으면 명시")
    procedure: str = Field(description="실험 절차를 순서대로 구체적으로")


def design_experiment(state: WorkflowState) -> dict:
    # equipment.py(⑤)가 짧은 목록이라는 전제로 조회 없이(SQL 조건 없이) 그대로
    # 프롬프트에 넣는다 — RoadMap "실험도구는 RDB, 자연어 탐색은 목록이 짧으니
    # 프롬프트에 넣으면 된다"는 결정을 여기서 실제로 쓴다.
    equipment_list = equipment.list_equipment()
    equipment_text = "\n".join(f"- {e['name']}: {e['purpose']}" for e in equipment_list) or "(등록된 장비 없음)"

    messages = [
        SystemMessage(content=EXPERIMENT_DESIGN_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"가설: {state.hypothesis}\n근거: {state.rationale}\n\n보유 장비 목록:\n{equipment_text}"
        )),
    ]
    result, _, disabled_models, tokens_used = invoke_with_fallback(
        state.model, messages, structured=ExperimentDesign, disabled_models=state.disabled_models
    )
    return {
        "independent_variable": result.independent_variable,
        "dependent_variable": result.dependent_variable,
        "controlled_variables": result.controlled_variables,
        "equipment_needed": result.equipment_needed,
        "procedure": result.procedure,
        "disabled_models": disabled_models,
        "tokens_used": _add_tokens(state.tokens_used, tokens_used),
    }


EXPERIMENT_ANALYSIS_SYSTEM_PROMPT = """가설·예측·실험 절차와 사용자가 보고한 실제
실험 결과를 비교해서 분석해라. 결과가 예측(testable_prediction)을 지지하는지,
반박하는지, 판단하기엔 불충분한지 이유와 함께 적어라. 결과가 예측과 어긋나거나
결론을 내리기에 불충분하면(측정 오류·통제 미흡 등) 재설계가 필요하다고 판단해라 —
애매하면 재설계 권장 쪽으로(잘못된 결론을 그대로 받아들이는 것보다 안전하다)."""


class ExperimentAnalysis(BaseModel):
    analysis: str = Field(description="결과가 예측을 지지/반박/불충분한지와 그 이유")
    needs_redesign: bool = Field(description="실험을 다시 설계해야 하면 True")


def analyze_results(state: WorkflowState) -> dict:
    # experiment_results는 사용자가 입력한 값 그대로 쓴다 — LLM이 실험을 "했다고
    # 치는" 게 아니라 실제로 사람이 하고 온 결과를 분석만 한다(가설/설계 노드와
    # 성격이 다른 지점).
    messages = [
        SystemMessage(content=EXPERIMENT_ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"가설: {state.hypothesis}\n예측: {state.testable_prediction}\n"
            f"실험 절차: {state.procedure}\n\n실제 실험 결과: {state.experiment_results}"
        )),
    ]
    result, _, disabled_models, tokens_used = invoke_with_fallback(
        state.model, messages, structured=ExperimentAnalysis, disabled_models=state.disabled_models
    )
    return {
        "analysis": result.analysis,
        "needs_redesign": result.needs_redesign,
        "disabled_models": disabled_models,
        "tokens_used": _add_tokens(state.tokens_used, tokens_used),
    }


find_operation_references = _make_reference_node(lambda s: s.analysis, "operation")


def route_by_stage(state: WorkflowState) -> str:
    return state.stage


graph = StateGraph(WorkflowState)
graph.add_node("generate_hypothesis", generate_hypothesis)
graph.add_node("find_hypothesis_references", find_hypothesis_references)
graph.add_node("design_experiment", design_experiment)
graph.add_node("find_design_references", find_design_references)
graph.add_node("analyze_results", analyze_results)
graph.add_node("find_operation_references", find_operation_references)
graph.add_conditional_edges(START, route_by_stage, {
    "hypothesis": "generate_hypothesis",
    "design": "design_experiment",
    "operation": "analyze_results",
})
graph.add_edge("generate_hypothesis", "find_hypothesis_references")
graph.add_edge("find_hypothesis_references", END)
graph.add_edge("design_experiment", "find_design_references")
graph.add_edge("find_design_references", END)
graph.add_edge("analyze_results", "find_operation_references")
graph.add_edge("find_operation_references", END)

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
            config = {"configurable": {"thread_id": "test"}}

            # 1단계: 가설 생성 — 그래프 정식 invoke(fresh thread라 START부터)
            result = await app.ainvoke(
                {"topic": "그래핀의 전기전도도는 온도에 어떻게 의존하는가"}, config=config,
            )
            print("가설:", result["hypothesis"])
            print("근거:", result["rationale"])
            print("예측:", result["testable_prediction"])
            print("참고문헌(가설):", [r["title"] for r in result["references"]])
            print("안내:", result["comment"])

            # 2단계: "설계 진행" 트리거 — stage 갱신을 새 invoke 호출 하나에 담으면
            # 라우터가 design_experiment로 보낸다(main.py가 실제로 쓸 패턴).
            design_result = await app.ainvoke({"stage": "design"}, config=config)
            print("독립변수:", design_result["independent_variable"])
            print("종속변수:", design_result["dependent_variable"])
            print("통제변수:", design_result["controlled_variables"])
            print("필요 장비:", design_result["equipment_needed"])
            print("절차:", design_result["procedure"])
            print("참고문헌(설계까지):", [r["title"] for r in design_result["references"]])
            print("안내:", design_result["comment"])

            # 3단계: 실험 운영 — 사람이 실제로 실험하고 온 결과를 입력하며 트리거.
            final = await app.ainvoke(
                {"stage": "operation", "experiment_results": "온도를 낮췄더니 저항이 예측과 달리 거의 변하지 않았다"},
                config=config,
            )
            print("분석:", final["analysis"])
            print("재설계 필요:", final["needs_redesign"])
            print("참고문헌(전체):", [r["title"] for r in final["references"]])
            print("안내:", final["comment"])

    asyncio.run(_smoke_test())
