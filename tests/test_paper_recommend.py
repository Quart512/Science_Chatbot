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
    def _fake_search(query, max_results=5):
        captured["query"] = query
        return []
    monkeypatch.setattr(paper_search, "search_papers", _fake_search)

    paper_recommend.recommend_for_interest(1)

    assert captured["query"] == "새로운 상전이"


def test_falls_back_to_title_when_looking_for_empty(monkeypatch):
    interest = {**INTEREST, "looking_for": ""}
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: interest)
    captured = {}
    monkeypatch.setattr(paper_search, "search_papers", lambda query, max_results=5: (captured.setdefault("query", query), [])[1])

    paper_recommend.recommend_for_interest(1)

    assert captured["query"] == "위상 물질"


def test_only_relevant_candidates_are_recorded_to_catalog(monkeypatch):
    # 07-31 재검토: 카탈로그 저장은 여전히 관련 있는 것만 — dismissed 신호 오염 방지
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda query, max_results=5: [_candidate("arxiv:1", "관련됨"), _candidate("arxiv:2", "무관함")],
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
        lambda query, max_results=5: [_candidate("arxiv:1", "관련됨"), _candidate("arxiv:2", "무관함")],
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
        lambda query, max_results=5: [
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
        lambda query, max_results=5: [_candidate("arxiv:fail"), _candidate("arxiv:ok")],
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
        lambda query, max_results=5: [_candidate("arxiv:1", "논문 제목", authors=["김", "이"], year="2020", doi="10.1/x")],
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


def test_no_candidates_returns_empty_list(monkeypatch):
    monkeypatch.setattr(interests, "get_interest", lambda interest_id, **kw: INTEREST)
    monkeypatch.setattr(paper_search, "search_papers", lambda query, max_results=5: [])

    assert paper_recommend.recommend_for_interest(1) == []
