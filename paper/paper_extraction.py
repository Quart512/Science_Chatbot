# 논문 요약기(②a)의 구조화 추출 스키마(LLM structured output, graph.py의 verify와 같은
# 패턴). **결정론적으로 계산 가능한 값은 여기 넣지 않는다** — 스키마에 필드를 두면
# LLM이 반드시 채우고 모르면 지어낸다. paper_id(등록 시점에 이미 계산됨)·서지정보
# (arxiv API가 줌)·preprint 여부(journal_ref 유무)·출처 위치(chunk id로 사후 조립)는
# 전부 스키마 밖 메타데이터 조립 단계의 몫. 남은 필드는 전부 "본문을 읽어야만 아는 것"만.
# 품질 판정(타당성·신뢰도)은 만들지 않는다 — 판정이 아니라 추출만(RoadMap 참고).

from typing import Literal

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    kind: Literal["experimental", "theoretical", "simulation"] = Field(
        description="근거의 종류 — 실험/이론/시뮬레이션 중 하나. 애매하면 본문에서 가장 강조된 것 하나로."
    )
    detail: str = Field(
        description="조건·규모 등 세부사항(예: 표본 크기, 시뮬레이션 파라미터, 사용한 이론적 틀). "
        "본문에 없으면 지어내지 말고 빈 문자열로."
    )


class PaperExtraction(BaseModel):
    core_claims: list[str] = Field(
        description="핵심 주장 1~3개. 저자의 표현을 최대한 보존하고, 본문에 없는 내용을 추론해서 덧붙이지 마라."
    )
    evidence: list[Evidence] = Field(
        default_factory=list,
        description="주장을 뒷받침하는 근거의 종류와 세부사항.",
    )
    author_stated_limitations: list[str] = Field(
        default_factory=list,
        description="저자가 스스로 밝힌 한계 — limitations/discussion 섹션 등에서 저자가 직접 "
        "진술한 것만 추출해라. 네가 판단한 논문의 약점을 적지 마라(판단이 아니라 추출이다).",
    )
    unresolved_questions: list[str] = Field(
        default_factory=list,
        description="저자가 스스로 미해결이라고 언급한 지점. 마찬가지로 네 판단이 아니라 저자의 진술만.",
    )
    code_data_availability: str = Field(
        default="",
        description="저자가 코드나 데이터 공개를 언급했다면 그 내용을 그대로 옮겨라(예: 저장소 링크, "
        "'요청 시 제공' 등). 언급이 전혀 없으면 빈 문자열로 — 없다고 단정하지 말고 '언급 없음'과 "
        "'비공개'를 구분하지 못한다는 걸 빈 문자열이 알려준다.",
    )
