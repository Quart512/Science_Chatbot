# 연구 워크플로우(⑥) — 가설 수립 → 실험 설계 → 실험 운영을 잇는 별도 그래프.
# 오케스트레이터(챗) 그래프와 State를 공유하지 않는다 — README "그래프 3개"(챗·연구
# 워크플로우·추천 파이프라인) 구조대로 독립된 최상위 그래프다. 며칠씩 걸리는 상태
# 있는 작업이라 체크포인터 영속화가 전제라, orchestrator.py와 같은 패턴으로 컴파일 전
# graph 빌더와 CHECKPOINT_DB_PATH만 여기서 export한다 — 실제 컴파일(체크포인터 연결)은
# 호출부 몫이다. 아직 main.py에 엔드포인트가 없어 지금 이 그래프를 컴파일해 쓰는 건
# 아래 __main__ 스모크 테스트와 테스트뿐이다(UI는 ⑦까지 나온 뒤 한 번에 — RoadMap 참고).
#
# 가설 수립 → 실험 설계 → 실험 운영 → 실험 보고서 → 논문 초안까지 연결됐고, 안전
# 가드레일도 붙었다(check_equipment_precautions — interrupt_before를 안 쓴 근거는 그
# 함수 docstring). 인용-근거 일치 검증(마커 기반 정규식 체크)은 다음 단위.
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

from models import add_tokens, invoke_with_fallback
import equipment
import reference_recommender


class WorkflowState(BaseModel):
    topic: str  # 사용자가 준 연구 주제·질문
    # 지금 어느 단계인지 — START의 조건부 엣지가 이 값으로 라우팅한다. 기본값이
    # "hypothesis"라 처음 만드는 thread는 자동으로 가설 단계부터 시작하고, 사용자가
    # "다음 단계로"를 누르면 호출부가 이 필드(+필요하면 새 입력)를 담아 다시 invoke하면 된다.
    stage: Literal["hypothesis", "design", "operation", "report", "writing"] = "hypothesis"
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
    # 값이라 LLM이 만들지 않는다(가설/설계와 성격이 다름). analysis/outcome은
    # 그 결과를 testable_prediction과 비교해 LLM이 뽑는다.
    experiment_results: str = ""
    analysis: str = ""
    # 결과가 예측과 어긋났을 때 "왜"를 구분한다(08-03, 사용자 지적) — 예전엔
    # needs_redesign: bool 하나뿐이라 "재설계해야 하는가"만 답했는데, 실제로 재실험을
    # 요청하는 이유가 갈래마다 다르고 사람이 다음에 할 일도 다르다: 가설의 전제 자체가
    # 틀렸으면 가설부터, 설계가 가설을 제대로 못 검증했으면 재설계, 실행 과정 문제면
    # 같은 설계로 재실행, 결과 서술이 불충분해 판단이 어려우면 재분석만 하면 된다.
    # needs_redesign은 outcome != "supported"로 100% 파생되는 값이라 따로 안 둔다.
    # Literal로 안 하고 str인 이유: 분석 전 기본값("")이 이 다섯 값 중 어디에도 속하지
    # 않는 "아직 없음" 상태라 — WorkflowState의 다른 결과 필드(hypothesis 등)와 같은 패턴.
    outcome: str = ""
    # 실험 보고서(⑦ 착수, 08-03) — LLM 호출 없이 위 필드들을 헤더 붙여 이어붙인 결정론적
    # 산출물(compile_experiment_report 참고). 논문 작성 단계는 5개 필드를 따로 읽는 대신
    # 이 하나만 읽는다 — 인터페이스가 단순해지고, 자체 검토(Evaluator-Optimizer)가 초안을
    # 대조할 "사실 기준선"이 하나로 명확해진다. LLM 재종합을 안 쓴 이유: 이미 각 필드가
    # 앞선 LLM 호출이 만든 완결된 문장이라, 다시 종합하면 요약 재귀 분할에서 우려한 것과
    # 같은 위험(재종합 과정에서 사실이 조용히 바뀜)만 새로 생기고 얻는 게 적다.
    experiment_report: str = ""
    # 논문 초안(⑦, 08-03) — draft_paper()가 experiment_report+references만 보고 채운다.
    # results는 사실만, discussion에서 해석 — 표준 논문 절 구성과 같은 구분.
    title: str = ""
    abstract: str = ""
    introduction: str = ""
    methods: str = ""
    results: str = ""
    discussion: str = ""
    # 본문의 [CITE:paper_id] 마커와 별개 채널 — 마커는 "어디에 인용이 붙는지"(렌더링·구조
    # 검증용), 이 목록은 "왜 인용했는지"(사람이 인용의 타당성을 검토할 근거). 각 항목:
    # {"paper_id", "reasoning"}. 인용-근거 일치를 LLM으로 재검증하지 않기로 한 이유
    # (08-03, 사용자 판단): 검증 LLM도 결국 ②a가 LLM으로 뽑아둔 요약을 보고 판단하므로
    # "LLM이 LLM을 검사"하는 구조라 새 근거가 안 생긴다 — 초안 쓴 LLM이 왜 인용했는지
    # 남기고 최종 판단은 사람이 한다("판정 대신 추출/신호" 원칙과 같은 결).
    citations: list[dict] = Field(default_factory=list)
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


# 각 단계의 산출물 필드 — 08-04 실사용 중 발견한 버그(RoadMap 참고) 수정에 쓴다: 어느
# 단계의 진입 노드든 자기 필드만 반환하고 뒤 단계 필드는 손을 안 대서, "report까지 만든
# 뒤 design으로 되돌아가 고치기"를 해도 operation/report 필드가 그대로 남아 화면
# 타임라인 체크가 안 꺼졌다. references는 예외(누적이 원래 설계, 체크포인트 복원
# 설계 노트와 같은 결)라 여기 안 넣는다.
_STAGE_ORDER = ("hypothesis", "design", "operation", "report", "writing")
_STAGE_FIELDS = {
    "hypothesis": ("hypothesis", "rationale", "testable_prediction"),
    "design": ("independent_variable", "dependent_variable", "controlled_variables", "equipment_needed", "procedure"),
    "operation": ("experiment_results", "analysis", "outcome"),
    "report": ("experiment_report",),
    "writing": ("title", "abstract", "introduction", "methods", "results", "discussion", "citations"),
}


def _reset_downstream_fields(stage: str) -> dict:
    """stage보다 뒤에 있는 단계들의 산출물 필드를 전부 기본값으로 돌리는 dict를 만든다.
    각 단계의 진입 노드(generate_hypothesis 등)가 자기 반환값에 그대로 얹으면, 그 노드가
    어느 경로(과거 체크포인트 복원이든 tip에서 바로 이전 단계로 진행이든)로 실행되든
    상관없이 낡은 하위 단계 값이 저절로 지워진다."""
    idx = _STAGE_ORDER.index(stage)
    reset = {}
    for later_stage in _STAGE_ORDER[idx + 1:]:
        for field in _STAGE_FIELDS[later_stage]:
            reset[field] = [] if field == "citations" else ""
    return reset


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
        "comment": "",  # 이전 실행이 남긴 comment가 안 지워지고 계속 이어붙던 버그 수정(08-04)
        "disabled_models": disabled_models,
        "tokens_used": add_tokens(state.tokens_used, tokens_used),
        **_reset_downstream_fields("hypothesis"),
    }


def _make_reference_node(get_text: Callable[["WorkflowState"], str], stage_name: str):
    """참고문헌 추천 노드를 찍어내는 클로저 팩토리 — tool.py의 make_search_tool과 같은
    패턴(그쪽은 site별 검색 tool, 여긴 단계별 참고문헌 노드). 스테이지마다 하는 일은
    "자기 산출물 텍스트로 검색해서 공유 references에 누적"으로 완전히 같고, 다른 건
    어느 필드(들)를 검색어로 쓰는지와 added_by_stage 값뿐이라 그때그때 복붙하는 대신
    get_text(state)로 위임한다.

    실패는 이 단계만 건너뛴다 — 앞 단계 산출물은 이미 나왔으므로 참고문헌 하나 못
    찾았다고 워크플로우 전체를 실패시킬 이유가 없다(삭제된 관심사 자동 제안 훅이 쓰던
    것과 같은 논리: 부가 기능 실패가 핵심 결과를 막지 않는다). 여기서 노드가 예외를
    던지면 방금 LLM으로 만든 가설·설계가 체크포인트에 커밋되지 못하고 통째로 날아간다.

    `RuntimeError`(모델 소진)·`ReferenceSearchError`(arxiv 검색 오류)를 각각 구분해서
    잡고, 그 아래 `Exception`도 여전히 잡는다 — recommend_references가 부르는 경로가
    paper_search → arxiv_api라 예상 못 한 예외가 새어나올 수 있는데(어댑터를 갈아끼울
    때마다 예외 타입 목록이 늘어나는 걸 막으려 이전부터 `Exception`을 최종 방어선으로
    잡아왔다), 08-04부터는 사용자에게 실패 사유를 4갈래로 구분해 보여주려고(RoadMap
    "참고문헌만 재검색 + 실패 사유 표시") 그 위에 두 타입을 먼저 잡는 게 추가됐다. 잡은
    예외 타입은 여전히 로그에 남겨 조용히 삼키지는 않는다.

    "이미 증명된 이론·이미 한 실험인지"는 LLM이 판정하지 않는다 — 찾은 참고문헌(이미
    screen_candidate의 연관성 근거가 붙어 있음)을 사람이 직접 읽고 템플릿을 고치거나
    재생성할지 판단하도록 comment로 안내만 한다.

    이 노드는 워크플로우에서 LLM을 가장 많이 부르는 지점(검색어 추출 1 + 스크리닝 N)이라
    disabled_models·tokens_used도 다른 노드와 똑같이 State에 반영한다 — 안 하면 앞
    단계에서 죽은 모델을 여기서 매 후보마다 다시 때려본다.

    comment는 기존 값을 지우지 않고 뒤에 이어붙인다(check_equipment_precautions와 같은
    합성 패턴, 방향만 반대) — operation 체인에서 이 노드 앞에 analyze_results가 갈래별
    안내를 이미 남겨두는데, 여기서 덮어쓰면 그 안내가 다음 노드로 못 넘어간다.
    """
    def node(state: WorkflowState) -> dict:
        def _with_prior_comment(text: str) -> str:
            return f"{state.comment}\n\n{text}" if state.comment else text

        # 예외 3갈래(③④, 검색어 추출 단계 포함)를 각각 다른 문구로 안내 — RuntimeError가
        # ReferenceSearchError보다 먼저 와야 하는 순서 제약은 없다(서로 다른 계통이라
        # 교집합 없음), 그냥 구체적인 타입을 Exception보다 먼저 잡아야 한다.
        try:
            found, reason, disabled_models, tokens_used = reference_recommender.recommend_references(
                get_text(state), disabled_models=state.disabled_models
            )
        except RuntimeError as e:
            print(f"참고문헌 추천 실패, 모델 소진(이 단계는 건너뜀): {type(e).__name__}: {e}")
            # 실패해도 disabled_models는 못 건진다 — 예외를 던진 시점의 갱신값이 호출
            # 스택과 함께 사라지기 때문(살리려면 예외에 실어 보내야 하는데, 그건 정상
            # 경로가 아닌 곳에 데이터를 태우는 설계라 안 한다). 다음 단계가 다시 판단한다.
            return {"comment": _with_prior_comment(
                "AI 모델이 모두 소진돼 참고문헌을 찾지 못했습니다 — 잠시 후 재생성해주세요."
            )}
        except reference_recommender.ReferenceSearchError as e:
            print(f"참고문헌 추천 실패, arxiv 검색 오류(이 단계는 건너뜀): {type(e).__name__}: {e}")
            return {"comment": _with_prior_comment(
                "arXiv 검색 중 오류가 발생했습니다 — 잠시 후 재생성해주세요."
            )}
        except Exception as e:
            print(f"참고문헌 추천 실패(이 단계는 건너뜀): {type(e).__name__}: {e}")
            return {"comment": _with_prior_comment("참고문헌 추천에 실패했습니다 — 직접 템플릿을 검토해주세요.")}

        existing_ids = {r["paper_id"] for r in state.references}
        new_entries = [
            {**r, "added_by_stage": stage_name} for r in found if r["paper_id"] not in existing_ids
        ]

        if new_entries:
            comment = (
                "참고논문을 확인해서 선행 연구된 내용이 있는지 확인하고 템플릿을 채우거나 "
                "수정해주세요. 참고문헌이 부족하다면 재생성을 눌러주세요."
            )
        elif found:
            # found는 있었지만 전부 이미 references에 있던 것(dedup) — 검색은 성공했으니
            # reason으로 구분할 실패가 아니다. 기존 문구 그대로.
            comment = "참고문헌을 찾지 못했습니다 — 재생성을 눌러 다시 시도하거나 직접 템플릿을 채워주세요."
        else:
            # found가 애초에 비어 있었던 경우만 reason으로 4갈래 중 ①②를 구분한다
            # (③④는 위에서 예외로 이미 처리됨).
            comment = {
                "no_candidates": "검색 결과가 없습니다 — 재생성을 눌러 다시 시도하거나 직접 템플릿을 채워주세요.",
                "all_irrelevant": "찾은 논문이 모두 관련성이 낮다고 판단됐습니다 — 재생성을 눌러 다시 시도하거나 직접 템플릿을 채워주세요.",
                "models_exhausted": "AI 모델이 모두 소진돼 후보 논문을 평가하지 못했습니다 — 잠시 후 재생성해주세요.",
            }.get(reason, "참고문헌을 찾지 못했습니다 — 재생성을 눌러 다시 시도하거나 직접 템플릿을 채워주세요.")

        return {
            "references": state.references + new_entries,
            "comment": _with_prior_comment(comment),
            "disabled_models": disabled_models,
            "tokens_used": add_tokens(state.tokens_used, tokens_used),
        }

    return node


find_hypothesis_references = _make_reference_node(lambda s: s.hypothesis, "hypothesis")
find_design_references = _make_reference_node(lambda s: s.procedure, "design")


EXPERIMENT_DESIGN_SYSTEM_PROMPT = """주어진 가설을 검증할 실험을 설계해라. 독립변수·
종속변수·통제변수를 명확히 구분하고, 실험 절차를 구체적인 순서로 적어라. 특히 함께
주어지는 "예측"이 실제로 측정 가능하도록 설계해라 — 실험이 끝난 뒤 그 예측이 맞았는지
틀렸는지 판단할 수 없는 설계는 가설을 검증하지 못한다. 필요한 장비는 아래 "보유 장비
목록"에 있는 것을 최우선으로 활용하고, 목록에 없는 장비가 꼭 필요하면 그것도 적되
목록에 없다는 걸 명시해라."""


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
        # testable_prediction을 같이 넣는 이유: 다음 단계(analyze_results)가 "결과가 이
        # 예측을 지지하는가"로 성패를 판정하는데, 정작 그 예측을 측정 가능하게 만들어야
        # 할 설계 단계가 예측을 못 보고 짜이면 검증할 수 없는 실험이 나온다.
        HumanMessage(content=(
            f"가설: {state.hypothesis}\n근거: {state.rationale}\n"
            f"예측: {state.testable_prediction}\n\n보유 장비 목록:\n{equipment_text}"
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
        "comment": "",
        "disabled_models": disabled_models,
        "tokens_used": add_tokens(state.tokens_used, tokens_used),
        **_reset_downstream_fields("design"),
    }


EXPERIMENT_ANALYSIS_SYSTEM_PROMPT = """가설·예측·실험 절차와 사용자가 보고한 실제
실험 결과를 비교해서 분석해라. 결과가 예측(testable_prediction)을 지지하는지,
반박하는지, 판단하기엔 불충분한지 이유와 함께 적어라.

지지하지 않는다면(반박·불충분 모두 포함) 그 이유를 아래 네 갈래 중 가장 가능성 높은
하나로 분류해라 — 갈래마다 사용자가 다음에 해야 할 일이 다르므로 애매해도 반드시
하나를 골라라:
- hypothesis_wrong: 가설의 전제(이론) 자체가 틀렸다고 보인다
- design_flawed: 전제는 맞지만 실험 설계(변수·통제·측정 방식)가 가설을 제대로 검증하지 못한다
- execution_error: 설계는 맞지만 실행 과정에서 오류가 있었다고 보인다(오염·조작 실수 등)
- analysis_error: 실험 자체엔 문제가 없어 보이나 결과 서술이 불충분해 판단하기 어렵다

analysis에 분류 근거도 함께 적어라(별도 필드로 안 나눔 — 같은 이유를 두 번 쓰게 되는
낭비를 피한다)."""


class ExperimentAnalysis(BaseModel):
    analysis: str = Field(description="결과가 예측을 지지/반박/불충분한지와 그 이유, 반박·불충분이면 outcome 분류 근거도 포함")
    outcome: Literal["supported", "hypothesis_wrong", "design_flawed", "execution_error", "analysis_error"] = Field(
        description="예측을 지지하면 supported, 아니면 네 갈래 중 가장 가능성 높은 원인 하나"
    )


# analyze_results가 채우는 comment — LLM이 자유롭게 쓰지 않고 코드가 고정 문구로 채운다
# (WorkflowState.comment 필드 설명과 같은 원칙: "결정론적 안내 문구... LLM이 아니라
# 코드가 채움"). outcome 값 자체는 LLM 판정이지만, 그 판정에 사람이 뭘 해야 하는지
# 안내하는 문장은 결정론적으로 고정해서 모델·문구 변동과 무관하게 일관되게 만든다.
OUTCOME_GUIDANCE = {
    "supported": "예측이 지지됐습니다.",
    "hypothesis_wrong": "가설의 전제 자체가 틀렸을 수 있습니다 — 가설부터 다시 세우는 걸 권장합니다.",
    "design_flawed": "실험 설계에 문제가 있어 보입니다 — 재설계를 눌러주세요.",
    "execution_error": "실행 과정에 문제가 있어 보입니다 — 같은 설계로 다시 실험하고 결과를 입력해주세요.",
    "analysis_error": "결과가 충분히 전달되지 않았을 수 있습니다 — 결과를 더 구체적으로 적어 다시 제출해주세요.",
}

# compile_experiment_report()가 보고서 본문에 쓰는 표시용 한글 라벨 — outcome 원값(영문
# 코드)은 라우팅·비교에 쓰고, 사람이 읽는 문서엔 이 라벨을 쓴다(관심사 다르면 값도 분리).
OUTCOME_LABELS = {
    "supported": "예측 지지됨",
    "hypothesis_wrong": "가설 전제 오류로 추정",
    "design_flawed": "실험 설계 결함으로 추정",
    "execution_error": "실행 과정 오류로 추정",
    "analysis_error": "결과 서술 불충분으로 판단 어려움",
    "": "(미분석)",
}


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
        "outcome": result.outcome,
        "comment": OUTCOME_GUIDANCE[result.outcome],
        "disabled_models": disabled_models,
        "tokens_used": add_tokens(state.tokens_used, tokens_used),
        **_reset_downstream_fields("operation"),
    }


find_operation_references = _make_reference_node(lambda s: s.analysis, "operation")

# 참고문헌만 독립 재시도(⑥, RoadMap "참고문헌만 재검색 + 실패 사유 표시" Part B)용 —
# main.py의 재시도 엔드포인트가 tip의 stage만 보고 어느 노드를 다시 부를지 찾는다.
# report/writing은 참고문헌 노드가 없어(compile_experiment_report/draft_paper는 새
# 텍스트를 안 만들고 있는 걸 재배열/종합할 뿐이라 검색할 새 주장이 없음, 위 주석 참고)
# 이 매핑에 없다 — 호출부가 stage로 조회해 없으면 400으로 막는다.
REFERENCE_NODE_BY_STAGE: dict[str, Callable[["WorkflowState"], dict]] = {
    "hypothesis": find_hypothesis_references,
    "design": find_design_references,
    "operation": find_operation_references,
}


def compile_experiment_report(state: WorkflowState) -> dict:
    """실험 보고서 — 가설·설계·운영 단계가 이미 만들어둔 필드를 헤더 붙여 이어붙이기만
    한다. LLM 호출 없음(판정 대신 추출 원칙과 같은 결 — 여기선 추출조차 아니라 순수
    재포맷). 참고문헌 노드를 안 붙이는 이유: 새 텍스트를 만드는 게 아니라 있는 걸
    재배열할 뿐이라 검색할 새 주장이 없다.

    별도 stage로 둔 이유(설계·운영과 같은 결): 사람이 다음 단계(writing)로 넘어가기
    전에 보고서 내용을 검토할 틈을 준다 — operation 체인에 자동으로 끼워 넣으면
    그 틈이 사라진다.
    """
    report = f"""# 실험 보고서

## 가설
{state.hypothesis}
근거: {state.rationale}
예측: {state.testable_prediction}

## 실험 설계
- 독립변수: {state.independent_variable}
- 종속변수: {state.dependent_variable}
- 통제변수: {state.controlled_variables}
- 필요 장비: {state.equipment_needed}

### 절차
{state.procedure}

## 실험 결과
{state.experiment_results}

## 분석
{state.analysis}

판정: {OUTCOME_LABELS.get(state.outcome, state.outcome)}"""
    return {"experiment_report": report, "comment": "", **_reset_downstream_fields("report")}


WRITING_SYSTEM_PROMPT = """주어진 실험 보고서를 바탕으로 논문 초안을 작성해라. 보고서에
없는 내용을 지어내지 마라 — 논문은 보고서에 기록된 사실만 다뤄야 한다.

인용은 아래 "참고문헌 목록"에 있는 논문만 할 수 있다. 본문에서 인용할 때는 문장 끝에
[CITE:paper_id] 마커를 그대로 붙여라(예: "...것으로 알려져 있다[CITE:arxiv:2401.01234]."). 목록에
없는 논문을 인용하거나 마커 없이 참고문헌을 언급하지 마라. 인용을 하나 쓸 때마다
citations 목록에 그 paper_id와 왜 인용했는지(논문의 어떤 부분 때문인지)를 짧게 적어라 —
사람이 인용이 적절한지 검토할 때 참고할 근거다.

results는 측정된 사실만 서술하고(해석 없이), discussion에서 그 결과가 예측을 지지·
반박·불충분하게 하는지와 그 이유(보고서의 "판정"을 참고), 필요하면 참고문헌과의
비교를 다뤄라."""


class CitationNote(BaseModel):
    paper_id: str = Field(description="인용한 논문의 paper_id — 참고문헌 목록에 있는 값 중 하나")
    reasoning: str = Field(description="이 논문을 왜 인용했는지, 논문의 어떤 부분 때문인지")


class PaperDraft(BaseModel):
    title: str = Field(description="논문 제목")
    abstract: str = Field(description="초록 — 배경·방법·결과·결론을 한 문단으로 요약")
    introduction: str = Field(description="서론 — 배경과 가설, 필요하면 참고문헌 인용")
    methods: str = Field(description="방법 — 실험 설계와 절차")
    results: str = Field(description="결과 — 측정된 사실만 서술(해석 없이)")
    discussion: str = Field(description="고찰 — 결과가 예측을 지지/반박/불충분하게 하는지와 그 이유")
    citations: list[CitationNote] = Field(
        default_factory=list, description="본문에서 [CITE:paper_id]로 인용한 논문마다 하나씩"
    )


def draft_paper(state: WorkflowState) -> dict:
    """논문 초안(⑦) — experiment_report(사실 기준선)와 references(인용 가능 목록)만
    보고 구조화된 초안을 뽑는다. 인용-근거 일치는 LLM으로 재검증하지 않는다(citations
    필드 주석 참고) — 다음 단위(정규식 기반 구조 검증: 마커의 paper_id가 실제로
    references에 있는지)만 결정론적으로 확인한다.
    """
    references_text = "\n".join(f"- {r['paper_id']}: {r['title']}" for r in state.references) or "(참고문헌 없음)"

    messages = [
        SystemMessage(content=WRITING_SYSTEM_PROMPT),
        HumanMessage(content=f"실험 보고서:\n{state.experiment_report}\n\n참고문헌 목록:\n{references_text}"),
    ]
    result, _, disabled_models, tokens_used = invoke_with_fallback(
        state.model, messages, structured=PaperDraft, disabled_models=state.disabled_models
    )
    return {
        "title": result.title,
        "abstract": result.abstract,
        "introduction": result.introduction,
        "methods": result.methods,
        "results": result.results,
        "discussion": result.discussion,
        "citations": [c.model_dump() for c in result.citations],
        "comment": "",
        "disabled_models": disabled_models,
        "tokens_used": add_tokens(state.tokens_used, tokens_used),
        **_reset_downstream_fields("writing"),
    }


def check_equipment_precautions(state: WorkflowState) -> dict:
    """안전 가드레일(08-02) — 설계된 장비 목록(equipment_needed)에 등록된 장비 이름이
    나오면 그 장비의 precautions를 찾아 comment 맨 앞에 붙인다. LLM 호출 없음(이름
    일치로 결정론적으로 찾음) — "안전한지 LLM이 판단"하는 게 아니라 "사람이 미리
    등록해둔 주의사항을 찾아서 보여주는" 것뿐이다(판정 대신 추출/신호 원칙과 같은 결).

    진짜 interrupt_before HITL은 안 쓴다 — 이 그래프는 물리적 행동을 하지 않고(사람이
    실험실에서 직접 함), 단계 전환 자체가 이미 사람 트리거라 자연스러운 승인 지점이
    있다. 그래서 여기서 할 일은 실행을 막는 게 아니라 그 판단 전에 경고를 놓치지
    않게 보여주는 것뿐 — comment 안내 패턴을 그대로 확장.

    설계·운영 두 단계 모두 이 노드를 거친다(README "설계·운영 양 단계 공통 조회") —
    equipment_needed는 설계 때 한 번 정해져 운영 때까지 state에 그대로 남아있으므로
    같은 노드를 두 체인 끝에 공유해서 붙인다.

    매칭은 부분 문자열 그대로 둔다 — "오실로스코프"가 "디지털 오실로스코프 2채널"에
    걸리는 게 정상 동작이고, 한국어는 정규식 단어 경계(\\b)가 사실상 안 먹는다. 과검출은
    안전 방향이라 오탐이 실제로 성가셔지기 전엔 규칙을 정교하게 만들지 않는다. 다만
    이름이 빈 문자열이면 `"" in x`가 항상 True라 모든 설계에 그 주의사항이 붙으므로
    그것만 막는다(컬럼이 NOT NULL이어도 ""는 통과하니 실제로 가능한 상태다).
    """
    notes = [
        f"[{item['name']}] {item['precautions']}"
        for item in equipment.list_equipment()
        if item["name"] and item["precautions"] and item["name"] in state.equipment_needed
    ]
    if not notes:
        return {}

    warning = "⚠️ 장비 주의사항:\n" + "\n".join(notes)
    return {"comment": f"{warning}\n\n{state.comment}" if state.comment else warning}


def route_by_stage(state: WorkflowState) -> str:
    return state.stage


graph = StateGraph(WorkflowState)
graph.add_node("generate_hypothesis", generate_hypothesis)
graph.add_node("find_hypothesis_references", find_hypothesis_references)
graph.add_node("design_experiment", design_experiment)
graph.add_node("find_design_references", find_design_references)
graph.add_node("analyze_results", analyze_results)
graph.add_node("find_operation_references", find_operation_references)
graph.add_node("check_equipment_precautions", check_equipment_precautions)
graph.add_node("compile_experiment_report", compile_experiment_report)
graph.add_node("draft_paper", draft_paper)
graph.add_conditional_edges(START, route_by_stage, {
    "hypothesis": "generate_hypothesis",
    "design": "design_experiment",
    "operation": "analyze_results",
    "report": "compile_experiment_report",
    "writing": "draft_paper",
})
graph.add_edge("generate_hypothesis", "find_hypothesis_references")
graph.add_edge("find_hypothesis_references", END)
graph.add_edge("design_experiment", "find_design_references")
graph.add_edge("find_design_references", "check_equipment_precautions")
graph.add_edge("analyze_results", "find_operation_references")
graph.add_edge("find_operation_references", "check_equipment_precautions")
graph.add_edge("check_equipment_precautions", END)
graph.add_edge("compile_experiment_report", END)
graph.add_edge("draft_paper", END)

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
            print("판정:", final["outcome"], "-", OUTCOME_GUIDANCE[final["outcome"]])
            print("참고문헌(전체):", [r["title"] for r in final["references"]])
            print("안내:", final["comment"])

            # 4단계: 보고서 — LLM 호출 없음(compile_experiment_report는 순수 재포맷).
            report_result = await app.ainvoke({"stage": "report"}, config=config)
            print("보고서:\n", report_result["experiment_report"])

            # 5단계: 논문 초안.
            draft = await app.ainvoke({"stage": "writing"}, config=config)
            print("제목:", draft["title"])
            print("초록:", draft["abstract"])
            print("서론:", draft["introduction"])
            print("방법:", draft["methods"])
            print("결과:", draft["results"])
            print("고찰:", draft["discussion"])
            print("인용 근거:", draft["citations"])

    asyncio.run(_smoke_test())
