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
    """관심사 하나를 기준으로 논문을 검색·스크리닝한다.

    start(08-11①, "추가 검색"): paper_search.search_papers()의 페이지네이션 오프셋을
    그대로 통과시킨다 — "지금 검색"을 반복 클릭해도 매번 같은 상위 결과가 나오는 대신,
    이미 받은 개수를 start로 넘기면 다음 순위 후보를 이어서 스크리닝할 수 있다.

    검색 쿼리는 관심사의 looking_for를 쓴다(비어 있으면 title로 폴백) — "찾는 것"이
    title보다 실제 검색 의도를 더 구체적으로 담고 있다.

    "카탈로그에 남기는 것"과 "화면에 보여주는 것"을 분리한다(07-31, 사용자 지적으로
    재검토) — 처음엔 관련 없다고 판정된 후보를 반환값에서도 통째로 뺐는데, 그러면
    스크리닝 LLM이 틀렸을 때(false negative — 실제로는 관련 있는데 관련 없다고 판정)
    사용자가 그 논문을 볼 기회 자체가 없어진다. reasoning도 이미 계산돼 있는데
    버려지는 낭비였다. 그래서:
      - **카탈로그 저장**은 그대로 관련 있는 것만 — dismissed는 "사용자가 직접
        기각했다"는 신호인데, 스크리닝이 미리 거른 것까지 섞으면 그 신호가 오염된다
        (로드맵 "기각 이력이 평가 기준의 정답 레이블" 설계 노트).
      - **반환 목록**은 관련 없다고 판정된 것도 포함 — "추천에서 끝나고 결정은
        사람이"라는 이 프로젝트의 기존 원칙과 일관되게, 최종 판단 기회를 사용자에게
        남긴다.

    반환 정렬은 관련도(is_relevant)를 유일한 기준으로만 쓴다(관련 있음이 앞) — 안정
    정렬이라 그 안에서는 검색 엔진이 준 원래 순서가 유지된다. peer_reviewed/
    citation_count/year는 서로 안 섞고 정렬에도 안 쓴다("스크리닝 축을 합치지
    않는다" 원칙, RoadMap 참고) — 그 축들로 어떻게 다시 정렬할지는 호출하는 쪽(UI)이
    고르면 된다.

    관심사가 없으면 ValueError. 후보 하나의 스크리닝이 실패해도(모델 소진 등) 그
    후보만 건너뛰고 나머지는 계속 진행한다 — 검색 자체가 실패한 것과 후보 하나가
    실패한 것은 다르게 다뤄야 한다(전자는 사용자에게 알릴 일, 후자는 부분 결과로 충분).
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
