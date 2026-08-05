# wikipedia_api.py의 JSON 파싱 톨게이트 테스트 — tests/test_arxiv_api.py와 같은 패턴.
# 네트워크 호출(_query_search)은 monkeypatch로 갈아끼우고 파싱·분기 로직만 검증.

import wikipedia_api
from wikipedia_api import _parse_search_response, wikipedia_search

SAMPLE_SEARCH_RESPONSE = {
    "batchcomplete": "",
    "query": {
        "pages": {
            "12345": {
                "pageid": 12345,
                "ns": 0,
                "title": "Quantum entanglement",
                "index": 1,
                "extract": "Quantum entanglement is the phenomenon that occurs when a group "
                "of particles interact in ways such that the quantum state of each particle "
                "cannot be described independently.",
                "fullurl": "https://en.wikipedia.org/wiki/Quantum_entanglement",
            },
            "67890": {
                "pageid": 67890,
                "ns": 0,
                "title": "Quantum computing",
                "index": 2,
                "extract": "Quantum computing is a type of computation that harnesses quantum mechanics.",
                "fullurl": "https://en.wikipedia.org/wiki/Quantum_computing",
            },
        }
    },
}

# 검색 결과가 없으면 "query" 키 자체가 없다(batchcomplete만 옴) — _parse_search_response()의
# .get() 체인이 이 형태를 빈 리스트로 처리하는지가 이 테스트의 핵심.
EMPTY_SEARCH_RESPONSE = {"batchcomplete": ""}


def test_parses_multiple_pages():
    pages = _parse_search_response(SAMPLE_SEARCH_RESPONSE)
    assert len(pages) == 2
    p = pages[0]
    assert p["title"] == "Quantum entanglement"
    assert p["url"] == "https://en.wikipedia.org/wiki/Quantum_entanglement"
    assert p["pageid"] == 12345
    assert "particles interact" in p["summary"]


def test_empty_response_returns_empty_list():
    assert _parse_search_response(EMPTY_SEARCH_RESPONSE) == []


def test_page_missing_extract_returns_empty_summary():
    # extract 필드가 아예 없는 문서(추출 실패 등) — None이 아니라 ""로 정규화되는지.
    response = {"query": {"pages": {"1": {"title": "짧은 문서", "pageid": 1}}}}
    pages = _parse_search_response(response)
    assert pages[0]["summary"] == ""


def test_wikipedia_search_forwards_query_and_limit(monkeypatch):
    captured = {}

    def _fake_query(params, _retries=1):
        captured.update(params)
        return SAMPLE_SEARCH_RESPONSE

    monkeypatch.setattr(wikipedia_api, "_query_search", _fake_query)
    results = wikipedia_search("quantum entanglement", max_results=2)

    assert captured["gsrsearch"] == "quantum entanglement"
    assert captured["gsrlimit"] == 2
    assert len(results) == 2


def test_wikipedia_search_returns_empty_list_when_no_matches(monkeypatch):
    monkeypatch.setattr(wikipedia_api, "_query_search", lambda params, _retries=1: EMPTY_SEARCH_RESPONSE)
    assert wikipedia_search("존재하지않는검색어xyz123") == []
