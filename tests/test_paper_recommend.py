"""
paper_recommend.py — 추천 검색(③) 오케스트레이션. interests/paper_search/paper_screening/
paper_catalog를 전부 몽키패치해 조립 로직만 검증 — 실제 LLM·네트워크·DB 없음.
"""
import pytest

import interests
import paper_catalog
import paper_recommend
import paper_screening
import paper_search

INTEREST = {"id": 1, "title": "위상 물질", "looking_for": "새로운 상전이", "already_known": "", "excluded_topics": ""}


@pytest.fixture(autouse=True)
def _stub_record_screening(monkeypatch):
    # record_screening()은 08-03에 추가된 실제 sqlite3 쓰기 호출 — 몽키패치 안 하면
    # 이 파일의 기존 테스트가 전부 실제 data/app.db를 건드린다(paper_ingest.py의
    # mark_owned 스텁 fixture와 같은 이유). 인자 검증이 필요한 테스트는 개별적으로
    # 다시 monkeypatch해서 이 기본값을 덮어쓴다.
    monkeypatch.setattr(paper_catalog, "record_screening", lambda *a, **kw: None)


def _candidate(paper_id="arxiv:1", title="논문", **overrides):
    base = {
        "paper_id": paper_id, "doi": None, "arxiv_id": "1", "title": title,
        "authors": ["김"], "year": "2024", "abstract": "초록", "pdf_url": "",
        "journal_ref": "", "citation_count": None,
    }
    base.update(overrides)
    return base


def _screened(paper_id, is_relevant, **overrides):
    base = {
        "paper_id": paper_id, "is_relevant": is_relevant, "reasoning": "이유",
        "peer_reviewed": False, "citation_count": None, "year": "2024",
    }
    base.update(overrides)
    return base


def test_raises_when_interest_not_found(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: None)

    with pytest.raises(ValueError):
        paper_recommend.recommend_for_interest(999)


def test_uses_looking_for_as_search_query(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    captured = {}
    def _fake_search(query, max_results=5, start=0):
        captured["query"] = query
        return []
    monkeypatch.setattr(paper_search, "search_papers", _fake_search)

    paper_recommend.recommend_for_interest(1)

    assert captured["query"] == "새로운 상전이"


def test_falls_back_to_title_when_looking_for_empty(monkeypatch):
    interest = {**INTEREST, "looking_for": ""}
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: interest)
    captured = {}
    monkeypatch.setattr(paper_search, "search_papers", lambda query, max_results=5, start=0: (captured.setdefault("query", query), [])[1])

    paper_recommend.recommend_for_interest(1)

    assert captured["query"] == "위상 물질"


def test_only_relevant_candidates_are_recorded_to_catalog(monkeypatch):
    # 07-31 재검토: 카탈로그 저장은 여전히 관련 있는 것만 — dismissed 신호 오염 방지
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda query, max_results=5, start=0: [_candidate("arxiv:1", "관련됨"), _candidate("arxiv:2", "무관함")],
    )

    def _fake_screen(candidate, interest, **kw):
        return _screened(candidate["paper_id"], candidate["paper_id"] == "arxiv:1")
    monkeypatch.setattr(paper_screening, "screen_candidate", _fake_screen)

    recorded = []
    monkeypatch.setattr(paper_catalog, "upsert_recommended", lambda paper_id, **kw: recorded.append(paper_id) or True)

    paper_recommend.recommend_for_interest(1)

    assert recorded == ["arxiv:1"]  # 무관한 후보는 카탈로그에 안 남음


def test_irrelevant_candidates_are_still_returned_not_hidden(monkeypatch):
    # 07-31 재검토: 반환 목록엔 관련 없다고 판정된 것도 포함 — LLM 판정이 틀렸을 때
    # (false negative) 사용자가 직접 보고 판단할 기회를 남긴다(카탈로그 저장과는 별개).
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda query, max_results=5, start=0: [_candidate("arxiv:1", "관련됨"), _candidate("arxiv:2", "무관함")],
    )
    monkeypatch.setattr(
        paper_screening, "screen_candidate",
        lambda candidate, interest, **kw: _screened(candidate["paper_id"], candidate["paper_id"] == "arxiv:1"),
    )
    monkeypatch.setattr(paper_catalog, "upsert_recommended", lambda paper_id, **kw: True)

    results = paper_recommend.recommend_for_interest(1)

    assert {r["paper_id"] for r in results} == {"arxiv:1", "arxiv:2"}  # 둘 다 반환됨


def test_results_sorted_by_relevance_only_preserving_original_order_within_groups(monkeypatch):
    # 관련도 하나만 정렬 기준으로 쓰고(관련 있음이 앞), 그 안에서는 검색 엔진이 준
    # 원래 순서를 유지해야 한다(peer_reviewed/citation_count/year로는 재정렬 안 함)
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda query, max_results=5, start=0: [
            _candidate("arxiv:1", "무관1"), _candidate("arxiv:2", "관련1"),
            _candidate("arxiv:3", "무관2"), _candidate("arxiv:4", "관련2"),
        ],
    )
    relevant_ids = {"arxiv:2", "arxiv:4"}
    monkeypatch.setattr(
        paper_screening, "screen_candidate",
        lambda candidate, interest, **kw: _screened(candidate["paper_id"], candidate["paper_id"] in relevant_ids),
    )
    monkeypatch.setattr(paper_catalog, "upsert_recommended", lambda paper_id, **kw: True)

    results = paper_recommend.recommend_for_interest(1)

    assert [r["paper_id"] for r in results] == ["arxiv:2", "arxiv:4", "arxiv:1", "arxiv:3"]


def test_screening_failure_skips_candidate_but_continues(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda query, max_results=5, start=0: [_candidate("arxiv:fail"), _candidate("arxiv:ok")],
    )

    def _fake_screen(candidate, interest, **kw):
        if candidate["paper_id"] == "arxiv:fail":
            raise RuntimeError("전 모델 소진 흉내")
        return _screened("arxiv:ok", True)
    monkeypatch.setattr(paper_screening, "screen_candidate", _fake_screen)
    monkeypatch.setattr(paper_catalog, "upsert_recommended", lambda paper_id, **kw: True)

    results = paper_recommend.recommend_for_interest(1)

    assert [r["paper_id"] for r in results] == ["arxiv:ok"]  # 실패한 후보만 빠지고 나머지는 처리됨


def test_passes_candidate_metadata_to_catalog(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda query, max_results=5, start=0: [_candidate("arxiv:1", "논문 제목", authors=["김", "이"], year="2020", doi="10.1/x")],
    )
    monkeypatch.setattr(paper_screening, "screen_candidate", lambda candidate, interest, **kw: _screened("arxiv:1", True))

    captured = {}
    def _fake_upsert(paper_id, **kw):
        captured["paper_id"] = paper_id
        captured.update(kw)
        return True
    monkeypatch.setattr(paper_catalog, "upsert_recommended", _fake_upsert)

    paper_recommend.recommend_for_interest(1)

    assert captured["paper_id"] == "arxiv:1"
    assert captured["title"] == "논문 제목"
    assert captured["authors"] == "김, 이"
    assert captured["year"] == "2020"
    assert captured["doi"] == "10.1/x"


def test_records_screening_for_both_relevant_and_irrelevant_candidates(monkeypatch):
    # 카탈로그(upsert_recommended, 관련 있는 것만)와 달리 interest_paper 기록은
    # 관련 없다고 판정된 것도 남겨야 한다 — "이 관심사에 무엇이 스크리닝됐나"의
    # 전체 기록이 목적(paper_catalog.py 상단 주석 참고).
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda query, max_results=5, start=0: [_candidate("arxiv:1", "관련됨"), _candidate("arxiv:2", "무관함")],
    )
    monkeypatch.setattr(
        paper_screening, "screen_candidate",
        lambda candidate, interest, **kw: _screened(candidate["paper_id"], candidate["paper_id"] == "arxiv:1", reasoning=f"{candidate['paper_id']} 근거"),
    )
    monkeypatch.setattr(paper_catalog, "upsert_recommended", lambda paper_id, **kw: True)

    recorded = []
    monkeypatch.setattr(
        paper_catalog, "record_screening",
        lambda interest_id, paper_id, *, is_relevant, reasoning, **kw: recorded.append((interest_id, paper_id, is_relevant, reasoning)),
    )

    paper_recommend.recommend_for_interest(1)

    assert (1, "arxiv:1", True, "arxiv:1 근거") in recorded
    assert (1, "arxiv:2", False, "arxiv:2 근거") in recorded  # 무관해도 기록됨


def test_screening_failure_does_not_record(monkeypatch):
    # 스크리닝 자체가 실패(RuntimeError)한 후보는 판정값이 없으니 당연히 기록하지 않는다.
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda query, max_results=5, start=0: [_candidate("arxiv:fail")],
    )
    def _boom(candidate, interest, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(paper_screening, "screen_candidate", _boom)

    recorded = []
    monkeypatch.setattr(
        paper_catalog, "record_screening",
        lambda *a, **kw: recorded.append((a, kw)),
    )

    paper_recommend.recommend_for_interest(1)

    assert recorded == []


def test_refresh_records_rescreening_result(monkeypatch):
    # refresh_for_interest의 재스크리닝 루프도 최신 판정을 기록해야 한다 — 관심사가
    # 수정돼 관련도가 바뀐 경우가 바로 이 경로에서 갱신된다.
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(paper_search, "search_papers", lambda query, max_results=5, start=0: [])
    monkeypatch.setattr(paper_catalog, "upsert_recommended", lambda paper_id, **kw: True)
    monkeypatch.setattr(
        paper_screening, "screen_candidate",
        lambda candidate, interest, **kw: _screened(candidate["paper_id"], False, reasoning="더는 관련 없음"),
    )

    recorded = []
    monkeypatch.setattr(
        paper_catalog, "record_screening",
        lambda interest_id, paper_id, *, is_relevant, reasoning, **kw: recorded.append((interest_id, paper_id, is_relevant, reasoning)),
    )

    paper_recommend.refresh_for_interest(1, [_existing("arxiv:1", is_relevant=True)])

    assert (1, "arxiv:1", False, "더는 관련 없음") in recorded


def test_no_candidates_returns_empty_list(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(paper_search, "search_papers", lambda query, max_results=5, start=0: [])

    assert paper_recommend.recommend_for_interest(1) == []


def test_forwards_start_offset_to_search(monkeypatch):
    # 08-11①, "추가 검색" — 이미 본 결과 다음부터 이어서 검색하기 위한 페이지네이션 오프셋
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    captured = {}
    def _fake_search(query, max_results=5, start=0):
        captured["start"] = start
        return []
    monkeypatch.setattr(paper_search, "search_papers", _fake_search)

    paper_recommend.recommend_for_interest(1, start=5)

    assert captured["start"] == 5


# --- refresh_for_interest() (08-11②, 관심사 수정 시 자동 재검색) ------------------


def _existing(paper_id, is_relevant=True, **overrides):
    base = {
        "paper_id": paper_id, "is_relevant": is_relevant, "reasoning": "이전 근거",
        "peer_reviewed": False, "citation_count": None, "year": "2023",
        "title": "기존 후보", "abstract": "기존 초록",
    }
    base.update(overrides)
    return base


def test_refresh_raises_when_interest_not_found(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: None)

    with pytest.raises(ValueError):
        paper_recommend.refresh_for_interest(999, [])


def test_refresh_drops_existing_candidates_no_longer_relevant(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(paper_search, "search_papers", lambda query, max_results=5, start=0: [])
    monkeypatch.setattr(paper_catalog, "upsert_recommended", lambda paper_id, **kw: True)

    # 재스크리닝 결과: arxiv:1만 여전히 관련 있음
    monkeypatch.setattr(
        paper_screening, "screen_candidate",
        lambda candidate, interest, **kw: _screened(candidate["paper_id"], candidate["paper_id"] == "arxiv:1"),
    )

    existing = [_existing("arxiv:1"), _existing("arxiv:2")]
    results = paper_recommend.refresh_for_interest(1, existing)

    assert [r["paper_id"] for r in results] == ["arxiv:1"]


def test_refresh_combines_kept_old_with_fresh_search(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda query, max_results=5, start=0: [_candidate("arxiv:new", "새 논문")],
    )
    monkeypatch.setattr(paper_catalog, "upsert_recommended", lambda paper_id, **kw: True)
    monkeypatch.setattr(
        paper_screening, "screen_candidate",
        lambda candidate, interest, **kw: _screened(candidate["paper_id"], True),
    )

    existing = [_existing("arxiv:old")]
    results = paper_recommend.refresh_for_interest(1, existing)

    assert {r["paper_id"] for r in results} == {"arxiv:old", "arxiv:new"}


def test_refresh_dedupes_when_fresh_search_repeats_kept_old_paper(monkeypatch):
    # 기존에서 살아남은 논문이 새 검색에서 다시 잡히면 새 쪽에서 제거 — 중복 표시 방지
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda query, max_results=5, start=0: [_candidate("arxiv:1", "같은 논문")],
    )
    monkeypatch.setattr(paper_catalog, "upsert_recommended", lambda paper_id, **kw: True)
    monkeypatch.setattr(
        paper_screening, "screen_candidate",
        lambda candidate, interest, **kw: _screened(candidate["paper_id"], True),
    )

    existing = [_existing("arxiv:1")]
    results = paper_recommend.refresh_for_interest(1, existing)

    assert [r["paper_id"] for r in results] == ["arxiv:1"]  # 한 번만


def test_refresh_does_not_reupsert_catalog_for_kept_old_candidates(monkeypatch):
    # 재스크리닝으로 살아남은 기존 후보는 doi/arxiv_id가 없어 카탈로그에 다시 안 넣는다 —
    # "카탈로그"와 "화면 표시" 분리 원칙 그대로. 새로 검색된 것만 upsert 대상.
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda query, max_results=5, start=0: [_candidate("arxiv:new", "새 논문")],
    )
    monkeypatch.setattr(
        paper_screening, "screen_candidate",
        lambda candidate, interest, **kw: _screened(candidate["paper_id"], True),
    )
    upserted = []
    monkeypatch.setattr(paper_catalog, "upsert_recommended", lambda paper_id, **kw: upserted.append(paper_id) or True)

    paper_recommend.refresh_for_interest(1, [_existing("arxiv:old")])

    assert upserted == ["arxiv:new"]  # arxiv:old는 재upsert 안 됨


def test_refresh_rescreen_failure_skips_candidate_but_continues(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(paper_search, "search_papers", lambda query, max_results=5, start=0: [])
    monkeypatch.setattr(paper_catalog, "upsert_recommended", lambda paper_id, **kw: True)

    def _fake_screen(candidate, interest, **kw):
        if candidate["paper_id"] == "arxiv:fail":
            raise RuntimeError("전 모델 소진 흉내")
        return _screened(candidate["paper_id"], True)
    monkeypatch.setattr(paper_screening, "screen_candidate", _fake_screen)

    existing = [_existing("arxiv:fail"), _existing("arxiv:ok")]
    results = paper_recommend.refresh_for_interest(1, existing)

    assert [r["paper_id"] for r in results] == ["arxiv:ok"]
