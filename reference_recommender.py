# 참고문헌 추천기 — 텍스트(초안 문단·답변)에서 검색어를 뽑아 참고할 논문 목록을 만든다.
# 연구 워크플로우 각 단계·논문 작성(⑦)·메인 챗(④) 온디맨드가 공용으로 쓸 함수
# (README "참고문헌 추천기" 참고) — 그래프 노드가 아니라 평범한 함수다.
#
# paper_search.search_papers()·paper_screening.screen_candidate()를 그대로 재사용한다
# (paper_recommend.recommend_for_interest()를 부르는 게 아니라 그 안의 부품만 공유 —
# 관심사는 "등록된 넓은 주제" 하나인데 이 함수는 "문장 하나"마다 불려야 해서 애초에
# 입력 성격이 다르다. RoadMap "참고문헌 추천기 착수" 08-02 참고).
#
# 보유 논문(VDB)을 먼저 보고 스크리닝 없이 채택한다 — 이미 라이브러리에 등록됐다는
# 것 자체가 신뢰 신호(파인만 QA의 retrieve()가 논문 VDB를 무조건 신뢰하는 것과 같은
# 결). 부족할 때만 신규 검색+스크리닝(②b)으로 보충한다. 서로 다른 신뢰 축이라 하나의
# 점수로 합쳐 재정렬하지 않고 보유 결과를 앞에 그대로 둔다("스크리닝 축을 합치지
# 않는다" 원칙과 같은 결).

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from models import invoke_with_fallback
from retrieval import papers_vectorstore
import paper_screening
import paper_search

EXTRACTION_MODEL = "gemini"

EXTRACTION_PROMPT = """주어진 텍스트를 읽고 참고문헌을 찾기 위한 검색어를 하나 뽑아라.
텍스트의 핵심 주장이나 개념을 논문 검색에 쓸 수 있는 간결한 구·문장으로 요약해라 —
텍스트에 실제로 있는 내용만 반영하고 없는 내용을 지어내지 마라."""


class SearchQuery(BaseModel):
    query: str = Field(description="논문 검색에 쓸 핵심 검색어")


def extract_search_query(text: str, *, model: str = EXTRACTION_MODEL) -> str:
    """text에서 검색어 하나를 뽑는다. 실패(모델 소진 등)는 RuntimeError를 그대로
    전파 — 검색어 자체가 없으면 이 함수를 호출한 recommend_references()가 통째로
    실패하는 게 맞다(빈 검색어로 검색해봤자 의미 없는 결과만 나옴)."""
    messages = [SystemMessage(content=EXTRACTION_PROMPT), HumanMessage(content=text)]
    result, _, _, _ = invoke_with_fallback(model, messages, structured=SearchQuery)
    return result.query


def recommend_references(text: str, *, max_results: int = 5, min_owned_results: int = 3) -> list[dict]:
    """text에서 검색어를 뽑아 참고문헌 후보 목록을 만든다.

    1. 보유 논문 VDB 우선 검색(papers_vectorstore) — 스크리닝 없이 그대로 채택.
    2. 보유 결과가 min_owned_results 미만이면 paper_search.search_papers()로 신규
       검색 → screen_candidate()로 관련도만 걸러 통과분만 추가(실패한 후보는 건너뜀,
       paper_recommend.py와 같은 정책).

    반환: 보유 결과가 먼저, 신규(관련 있는 것만) 결과가 뒤. 각 항목:
    {"paper_id", "title", "source": "owned" 또는 "external", 신규만 "reasoning"도 포함}.
    """
    query = extract_search_query(text)

    owned_hits = papers_vectorstore.similarity_search_with_score(query, k=max_results)
    seen_paper_ids: set[str] = set()
    owned_results = []
    for doc, _score in owned_hits:
        paper_id = doc.metadata.get("paper_id")
        if not paper_id or paper_id in seen_paper_ids:
            continue
        seen_paper_ids.add(paper_id)
        owned_results.append({
            "paper_id": paper_id,
            "title": doc.metadata.get("title", ""),
            "source": "owned",
        })

    external_results = []
    if len(owned_results) < min_owned_results:
        candidates = paper_search.search_papers(query, max_results=max_results)
        for candidate in candidates:
            if candidate["paper_id"] in seen_paper_ids:
                continue
            try:
                screened = paper_screening.screen_candidate(candidate, query)
            except RuntimeError as e:
                print(f"참고문헌 스크리닝 실패, 이 후보는 건너뜀(paper_id={candidate['paper_id']}): {type(e).__name__}: {e}")
                continue
            if screened["is_relevant"]:
                seen_paper_ids.add(candidate["paper_id"])
                external_results.append({
                    "paper_id": candidate["paper_id"],
                    "title": candidate["title"],
                    "source": "external",
                    "reasoning": screened["reasoning"],
                })

    return owned_results + external_results
