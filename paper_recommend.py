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


def refresh_for_interest(
    interest_id: int, existing_candidates: list[dict], *, max_results: int = 5, conn=None
) -> list[dict]:
    """관심사가 수정된 직후(08-11②) 자동으로 한 번 호출된다 — "수정한 내용이 크지
    않을 수도 있으니 기존에 검색했던 논문을 버리지 말고 재활용하자"는 사용자 지적을
    반영한다.

    existing_candidates: 프론트가 세션에 쌓아둔, 이전에 이 관심사로 검색해서 이미
    screen_candidate()를 한 번 거친 후보들(recommend_for_interest()가 반환하는 것과
    같은 형태 — paper_id/abstract/peer_reviewed/citation_count/year/title 포함).
    이들을 **수정된 관심사 기준으로 다시 스크리닝**해서 관련 있는 것만 남긴다(관련
    없어진 것은 버림 — "관련있다고 판단되는 건 남기자"). journal_ref 원본은 프론트에
    안 넘어가 있으므로(peer_reviewed로만 축약됨), screen_candidate()가 기대하는 후보
    형태로 역산해 넣는다 — peer_reviewed=True였으면 journal_ref에 아무 비어있지 않은
    문자열이나 넣으면 bool(journal_ref)가 다시 True로 복원된다(peer_reviewed 자체는
    관심사와 무관한 논문 고유 사실이라 재계산할 필요가 없다 — 그대로 보존하기 위한
    역산일 뿐, 다시 판정하는 게 아니다).

    동시에 recommend_for_interest()로 **새 페이지 하나(start=0)를 정상적으로 검색**
    한다 — 카탈로그 upsert도 그 경로가 기존과 똑같이 처리한다(새로 찾은 관련 논문은
    그대로 카탈로그에 남음). 재스크리닝으로 살아남은 기존 후보는 **카탈로그에 다시
    upsert하지 않는다** — 프론트가 들고 있던 후보엔 doi/arxiv_id가 애초에 없어(처음
    검색 때도 반환값엔 안 실었음) 정확한 메타데이터로 넣을 수 없고, "카탈로그에
    남기는 것"과 "화면에 보여주는 것"을 분리한다는 이 함수의 기존 원칙과도 맞는다.

    새 페이지 결과와 기존에서 살아남은 후보가 겹치면(같은 논문이 이번에도 검색됨)
    새 쪽에서 제거해 중복 표시를 막는다 — 기존 쪽이 이미 최신 관심사 기준으로
    재스크리닝된 값이라 그대로 유지.

    반환은 recommend_for_interest()와 같은 모양으로 관련도 하나만 기준으로 재정렬
    (기존에서 살아남은 것 + 새로 검색된 것 합쳐서).
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
