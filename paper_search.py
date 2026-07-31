# =========================================================
# 논문 검색 어댑터 — ③ 추천 검색·참고문헌 추천기가 공용으로 쓸 인터페이스(RoadMap "논문
# 검색 (어댑터)" 참고). 지금은 arxiv_api.py의 arxiv_search()만 뒤에 두지만, 나중에
# Crossref/OpenAlex로 교체할 때 호출하는 쪽이 이 함수 시그니처만 알면 되도록 격리한다 —
# pdf_parse.py(PyMuPDF 격리)·arxiv_api.py(langchain_community 우회) 때와 같은 어댑터 패턴.
#
# 반환 형태를 paper_catalog.py의 upsert_recommended()가 그대로 받아 쓸 수 있게 맞춘다 —
# paper_id는 여기서 미리 계산해둔다(paper/paper_id.py, arxiv_id 기준 — doi는 arxiv API가
# 주면 같이 쓰지만, doi가 있어도 arxiv preprint는 doi가 우선순위상 앞서더라도 실제로는
# "이 시점에 우리가 아는 게 arxiv_id뿐"인 경우가 대부분이라 결과 확인 후 판단할 것 — 지금은
# doi가 있으면 doi를 우선 쓴다, normalize_paper_id의 우선순위와 일관되게).
#
# citation_count는 항상 None이다 — 계산할 방법이 없다(RoadMap "외부 API는 최종 단계의
# 어댑터" 참고, OpenAlex 등을 붙이기 전까지는 값을 만들어낼 수 없으므로 빈 채로 둔다).
# journal_ref는 arxiv_search()가 실제로 채워준다(비어있으면 대부분 preprint 단계).
# =========================================================

from arxiv_api import arxiv_search
from paper.paper_id import normalize_paper_id


def search_papers(query: str, max_results: int = 5) -> list[dict]:
    """쿼리로 논문 후보를 검색해 paper_id·지표 자리까지 채운 통일된 형태로 반환한다.

    반환 키: paper_id, doi, arxiv_id, title, authors(list[str]), year, abstract,
    pdf_url, journal_ref, citation_count(항상 None).
    """
    results = arxiv_search(query, max_results=max_results)
    candidates = []
    for r in results:
        doi = r.get("doi") or None
        arxiv_id = r.get("arxiv_id") or None
        try:
            paper_id = normalize_paper_id(doi=doi, arxiv_id=arxiv_id)
        except ValueError:
            # arxiv_id가 파싱 실패 등으로 비어있는 기형 응답 — 실제로 걸릴 일은 거의 없지만
            # (arxiv 검색 결과는 항상 <id>를 준다) 하나가 죽었다고 나머지 후보까지 잃을
            # 이유는 없다(정직하게 실패하되, 국소적으로).
            print(f"paper_id를 계산할 수 없어 후보에서 제외: {r.get('title', '(제목 없음)')!r}")
            continue
        candidates.append({
            "paper_id": paper_id,
            "doi": doi,
            "arxiv_id": arxiv_id,
            "title": r["title"],
            "authors": r["authors"],
            "year": r["year"],
            "abstract": r["abstract"],
            "pdf_url": r["pdf_url"],
            "journal_ref": r.get("journal_ref", ""),
            "citation_count": None,
        })
    return candidates


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "quantum entanglement"
    for c in search_papers(query, max_results=3):
        print(f"[{c['paper_id']}] {c['title']} ({c['year']})")
        print(f"  journal_ref: {c['journal_ref'] or '(없음 — preprint로 보임)'}")
