"""
paper_search.py — 논문 검색 어댑터(08-09②). arxiv_search()를 몽키패치해 순수 조립 로직만
검증 — 실제 네트워크 호출 없음.
"""
import paper_search


def _fake_arxiv_result(**overrides):
    base = {
        "title": "테스트 논문",
        "authors": ["김", "이"],
        "year": "2024",
        "arxiv_id": "2401.12345",
        "abstract": "초록입니다.",
        "pdf_url": "https://arxiv.org/pdf/2401.12345",
        "journal_ref": "",
        "doi": "",
    }
    base.update(overrides)
    return base


def test_search_papers_computes_paper_id_from_arxiv_id(monkeypatch):
    monkeypatch.setattr(paper_search, "arxiv_search", lambda query, max_results=5, start=0: [_fake_arxiv_result()])

    candidates = paper_search.search_papers("quantum")

    assert len(candidates) == 1
    assert candidates[0]["paper_id"] == "arxiv:2401.12345"
    assert candidates[0]["arxiv_id"] == "2401.12345"
    assert candidates[0]["doi"] is None  # 빈 문자열이 아니라 None으로 정규화


def test_search_papers_prefers_doi_when_present(monkeypatch):
    # normalize_paper_id의 우선순위(DOI > arXiv)와 일관되게
    monkeypatch.setattr(
        paper_search, "arxiv_search",
        lambda query, max_results=5, start=0: [_fake_arxiv_result(doi="10.1234/xyz")],
    )

    candidates = paper_search.search_papers("quantum")

    assert candidates[0]["paper_id"] == "doi:10.1234/xyz"
    assert candidates[0]["doi"] == "10.1234/xyz"


def test_search_papers_citation_count_always_none(monkeypatch):
    monkeypatch.setattr(paper_search, "arxiv_search", lambda query, max_results=5, start=0: [_fake_arxiv_result()])

    candidates = paper_search.search_papers("quantum")
    assert candidates[0]["citation_count"] is None


def test_search_papers_carries_journal_ref_through(monkeypatch):
    monkeypatch.setattr(
        paper_search, "arxiv_search",
        lambda query, max_results=5, start=0: [_fake_arxiv_result(journal_ref="Phys. Rev. D 100, 1 (2024)")],
    )

    candidates = paper_search.search_papers("quantum")
    assert candidates[0]["journal_ref"] == "Phys. Rev. D 100, 1 (2024)"


def test_search_papers_skips_malformed_entry_without_id(monkeypatch):
    # arxiv_id도 doi도 없는 기형 응답 — paper_id를 계산할 수 없으므로 후보에서 빠져야 하고,
    # 나머지 정상 후보는 살아남아야 함
    monkeypatch.setattr(
        paper_search, "arxiv_search",
        lambda query, max_results=5, start=0: [
            _fake_arxiv_result(title="기형 응답", arxiv_id="", doi=""),
            _fake_arxiv_result(title="정상 응답"),
        ],
    )

    candidates = paper_search.search_papers("quantum")

    assert len(candidates) == 1
    assert candidates[0]["title"] == "정상 응답"


def test_search_papers_passes_query_and_max_results_through(monkeypatch):
    captured = {}
    def _fake_search(query, max_results=5, start=0):
        captured["query"] = query
        captured["max_results"] = max_results
        captured["start"] = start
        return []
    monkeypatch.setattr(paper_search, "arxiv_search", _fake_search)

    paper_search.search_papers("dark matter", max_results=10)

    assert captured == {"query": "dark matter", "max_results": 10, "start": 0}


def test_search_papers_forwards_start_offset(monkeypatch):
    # 08-11①, "추가 검색" — 이미 본 결과 다음부터 이어받기 위한 페이지네이션 오프셋
    captured = {}
    def _fake_search(query, max_results=5, start=0):
        captured["start"] = start
        return []
    monkeypatch.setattr(paper_search, "arxiv_search", _fake_search)

    paper_search.search_papers("dark matter", start=5)

    assert captured["start"] == 5
