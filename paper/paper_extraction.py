# =========================================================
# 논문 요약기(②a)의 구조화 추출 스키마 — LLM structured output(verify/final_answer_
# structure와 같은 패턴, graph.py 참고)에 쓸 Pydantic 모델. 실제로 이 스키마로
# LLM을 호출하는 노드/파이프라인은 아직 없음 — 스키마만 먼저 확정한다.
#
# 설계 원칙 (07-28, 실제 리뷰에서 나온 지적 반영): 이건 효율 문제가 아니라 안전
# 문제다. structured output 스키마에 필드를 넣으면 LLM은 반드시 그걸 채운다 —
# 모르면 그럴듯한 값을 지어낸다. 그래서 "LLM이 본문을 읽어야만 알 수 있는 것"만
# 이 스키마에 남기고, "우리가 이미 알고 있거나 계산으로 낼 수 있는 것"은 전부
# 스키마 밖(메타데이터 조립 단계)으로 뺐다:
#
#   - paper_id: 등록 시점에 이미 DOI/arxiv id/파일 바이트로 결정론적으로 계산됨
#     (paper_id.py의 normalize_paper_id) — LLM이 알 이유가 없고, 모르면 그럴듯한
#     DOI를 지어낼 위험이 있다. 이 값이 카탈로그 기본 키라 오염되면 "등록하면
#     추천에서 내려감" 매칭이 조용히 깨진다 — 토큰 낭비가 아니라 데이터 무결성 문제.
#   - preprint 여부: 본문을 읽어서 판단할 게 아니라 arXiv API의 journal_ref
#     필드 유무로 결정되는 사실 확인 — 메타데이터 조립 단계의 몫.
#   - 서지정보(제목·저자·연도): arxiv_search()가 이미 구조화된 값을 주므로,
#     본문 추출로 대체하지 않는다(추출이 더 부정확할 수 있다).
#   - from_section이 아니라 from_chunk: 이 스키마 자체에는 출처 필드를 두지
#     않는다. paper_sections.py가 청크마다 매기는 index로 호출하는 코드가
#     chunk id(f"{paper_id}-section-{index}")를 조립해 사후에 붙인다 — "어느
#     섹션에서 나왔나"를 헤더 라벨로 정확히 못 박으려 하지 않는다(한 청크가
#     여러 헤더를 묶고 있을 수 있어 애초에 불가능). 대신 RAG의 출처 표기처럼
#     "그 청크 전체를 다시 찾아볼 수 있는 위치"만 보장한다 — 검증(⑦)이 필요할
#     때 그 id로 원본 청크를 통째로 다시 가져와 읽으면 된다. 상세는
#     paper_sections.py의 모듈 docstring 참고.
#
# 반대로 이 스키마에 남은 필드들은 전부 "본문을 읽어야만 알 수 있는" 것들이다 —
# 예: "저자가 코드·데이터 공개를 언급했나"는 preprint 여부와 겉보기엔 비슷해
# 보이지만 arXiv 메타데이터엔 없는, 본문에서만 확인 가능한 정보라 그대로 남겼다.
#
# 품질 판정(과학적 타당성·신뢰도 점수)은 만들지 않는다 — 판정이 아니라 추출만
# 한다는 원칙은 RoadMap.md "논문 평가 기준" 설계 노트 참고.
# =========================================================

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
