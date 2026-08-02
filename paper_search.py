# 논문 검색 어댑터 — ③ 추천 검색·참고문헌 추천기가 공용으로 쓸 인터페이스. arxiv_api.py의
# arxiv_search()를 뒤에 두고, 나중에 Crossref/OpenAlex로 교체해도 호출부는 이 함수
# 시그니처만 알면 되게 격리한다. citation_count는 계산 방법이 없어 항상 None(OpenAlex
# 등을 붙이기 전까지, RoadMap "외부 API는 최종 단계의 어댑터" 참고).

from arxiv_api import arxiv_search
from paper.paper_id import normalize_paper_id


def search_papers(query: str, max_results: int = 5, start: int = 0) -> list[dict]:
    """쿼리로 논문 후보를 검색해 paper_id·지표 자리까지 채운 통일된 형태로 반환한다.

    반환 키: paper_id, doi, arxiv_id, title, authors(list[str]), year, abstract,
    pdf_url, journal_ref, citation_count(항상 None).

    start: arxiv_search()의 페이지네이션 오프셋을 그대로 통과시킨다 — "추가 검색"이
    이미 본 결과 다음부터 이어받을 수 있게(arxiv_api.py의 arxiv_search 참고).
    """
    results = arxiv_search(query, max_results=max_results, start=start)
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
