# =========================================================
# 추천 검색(③) — 관심사 하나를 받아 검색(paper_search)→스크리닝(paper_screening)→
# 카탈로그 기록(paper_catalog)을 엮는다. "관심사에서 트리거할 때만" 실행한다(cron
# 아님, RoadMap 참고) — main.py의 POST 엔드포인트가 사용자 요청으로만 호출.
# =========================================================

import interests
import paper_catalog
import paper_screening
import paper_search


def recommend_for_interest(interest_id: int, *, max_results: int = 5, start: int = 0, conn=None) -> list[dict]:
    """관심사 하나를 기준으로 논문을 검색·스크리닝한다. 검색 쿼리는 looking_for(비어
    있으면 title 폴백). start는 페이지네이션 오프셋("추가 검색"이 다음 순위부터 이어받게).

    **카탈로그 저장**(관련 있는 것만 — dismissed는 "사용자가 직접 기각"만을 위한
    신호라 스크리닝이 거른 것과 섞으면 오염됨)과 **반환 목록**(관련 없다고 판정된
    것도 포함 — false negative여도 사용자가 직접 볼 기회를 남김)을 분리한다.

    반환 정렬은 관련도만 기준(관련 있음이 앞, 안정 정렬이라 그 안 순서는 유지) —
    peer_reviewed/citation_count/year는 정렬에 안 섞는다("스크리닝 축을 합치지 않는다").

    관심사가 없으면 ValueError. 후보 하나의 스크리닝 실패는 그 후보만 건너뛴다.
    """
    interest = interests.get_interest(interest_id, conn=conn)
    if interest is None:
        raise ValueError(f"관심사 id={interest_id}를 찾을 수 없습니다")

    query = interest["looking_for"] or interest["title"]
    candidates = paper_search.search_papers(query, max_results=max_results, start=start)

    results = []
    for candidate in candidates:
        try:
            screened = paper_screening.screen_candidate(candidate, interest)
        except RuntimeError as e:
            print(f"스크리닝 실패, 이 후보는 건너뜀(paper_id={candidate['paper_id']}): {type(e).__name__}: {e}")
            continue

        if screened["is_relevant"]:
            paper_catalog.upsert_recommended(
                candidate["paper_id"],
                doi=candidate["doi"],
                arxiv_id=candidate["arxiv_id"],
                title=candidate["title"],
                authors=", ".join(candidate["authors"]) if candidate["authors"] else "",
                year=candidate["year"],
                conn=conn,
            )

        results.append({**screened, "title": candidate["title"], "abstract": candidate["abstract"]})

    results.sort(key=lambda r: not r["is_relevant"])
    return results


def refresh_for_interest(
    interest_id: int, existing_candidates: list[dict], *, max_results: int = 5, conn=None
) -> list[dict]:
    """관심사 수정 직후 호출 — 기존에 검색해둔 후보를 버리지 않고 새 기준으로
    재스크리닝해 관련 있는 것만 남긴 뒤, 새 페이지 하나(start=0)를 더 검색해 합친다.

    existing_candidates는 recommend_for_interest() 반환 형태(paper_id/abstract/
    peer_reviewed/citation_count/year/title). journal_ref 원본이 없어(peer_reviewed로만
    축약돼 전달됨) screen_candidate() 입력을 역산해 넣는다 — peer_reviewed=True면
    journal_ref에 아무 비어있지 않은 문자열을 넣어 bool() 복원만 하고 재계산은 안 함.

    재스크리닝으로 살아남은 후보는 doi/arxiv_id가 없어 카탈로그에 재upsert하지
    않는다(새로 검색된 것만 upsert). 겹치는 paper_id는 새 쪽에서 제거해 중복 방지.
    """
    interest = interests.get_interest(interest_id, conn=conn)
    if interest is None:
        raise ValueError(f"관심사 id={interest_id}를 찾을 수 없습니다")

    kept_old = []
    for c in existing_candidates:
        pseudo_candidate = {
            "paper_id": c.get("paper_id"),
            "abstract": c.get("abstract", ""),
            "journal_ref": "peer-reviewed" if c.get("peer_reviewed") else "",
            "citation_count": c.get("citation_count"),
            "year": c.get("year"),
        }
        try:
            screened = paper_screening.screen_candidate(pseudo_candidate, interest)
        except RuntimeError as e:
            print(f"재스크리닝 실패, 이 후보는 건너뜀(paper_id={c.get('paper_id')}): {type(e).__name__}: {e}")
            continue
        if screened["is_relevant"]:
            kept_old.append({**screened, "title": c.get("title", ""), "abstract": c.get("abstract", "")})

    seen_ids = {r["paper_id"] for r in kept_old}
    fresh = recommend_for_interest(interest_id, max_results=max_results, start=0, conn=conn)
    fresh = [r for r in fresh if r["paper_id"] not in seen_ids]

    combined = kept_old + fresh
    combined.sort(key=lambda r: not r["is_relevant"])
    return combined


if __name__ == "__main__":
    import sys

    title = sys.argv[1] if len(sys.argv) > 1 else "위상 물질"
    looking_for = sys.argv[2] if len(sys.argv) > 2 else "topological phase transition"

    interest_id = interests.create_interest(title, looking_for=looking_for)
    print(f"관심사 등록: id={interest_id}")

    results = recommend_for_interest(interest_id, max_results=3)
    print(f"추천된 논문 {len(results)}건:")
    for r in results:
        print(f"  [{r['paper_id']}] {r['title']}")
        print(f"    근거: {r['reasoning']}")
