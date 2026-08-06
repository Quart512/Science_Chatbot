# 위키백과 공식 API(https://en.wikipedia.org/w/api.php)를 requests로 직접 호출·파싱한다
# — arxiv_api.py와 같은 이유(langchain_community의 site 제한 DDG 검색은 스니펫만 주는
# 임시방편이었다, tool.py 참고)로 wikipedia PyPI 패키지(신뢰성 문제로 배제, RoadMap
# "tool 정비" 참고)도 안 쓰고 직접 구현한다.
#
# generator=search + prop=extracts를 한 번에 묶어 호출한다(action=query&list=search로
# 제목만 받고 각 문서를 다시 조회하는 2단계 대신) — arxiv_search()가 한 번의 요청으로
# 구조화된 결과를 다 받는 것과 같은 이유로 왕복을 줄인다.

import requests

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
# 위키미디어 API 에티켓 — User-Agent 없는 요청은 차단될 수 있음(arxiv_api.py와 같은 이유)
HEADERS = {"User-Agent": "AIsaac/0.1 (student project; contact: d3725gt@gmail.com)"}


def _parse_search_response(data: dict) -> list[dict]:
    """MediaWiki API JSON 응답을 구조화된 결과 리스트로 변환한다(네트워크 호출과
    분리 — 실제 API 없이 pytest 가능).

    검색 결과가 없으면 응답에 "query" 키 자체가 없다(batchcomplete만 옴) — .get()
    체인으로 빈 리스트 처리. "query.pages"는 pageid를 키로 하는 dict라 순서가
    보장된다는 공식 문서는 없지만, 실측상 generator=search의 검색 순위 순서를
    그대로 따른다(재정렬 로직을 따로 두지 않는 이유)."""
    pages = data.get("query", {}).get("pages", {})
    return [
        {
            "title": page.get("title", ""),
            "summary": (page.get("extract") or "").strip(),
            "url": page.get("fullurl", ""),
            "pageid": page.get("pageid", 0),
        }
        for page in pages.values()
    ]


def _query_search(params: dict, _retries: int = 1) -> dict:
    """위키백과 API에 요청을 보내고(429/5xx 재시도 포함) 파싱된 JSON을 반환한다."""
    for attempt in range(_retries + 1):
        try:
            resp = requests.get(WIKIPEDIA_API_URL, params=params, headers=HEADERS, timeout=10)
        except requests.exceptions.RequestException:
            if attempt < _retries:
                continue
            raise
        if resp.status_code in (429, 503) and attempt < _retries:
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("unreachable")  # for 루프가 항상 return이나 raise로 끝나 도달 안 함


def wikipedia_search(query: str, max_results: int = 3, _retries: int = 1) -> list[dict]:
    """위키백과(영문)를 검색해 구조화된 결과 리스트로 반환한다(반환 키는
    _parse_search_response 참고). 결과가 없으면 빈 리스트."""
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": max_results,
        "prop": "extracts|info",
        "exintro": True,
        "explaintext": True,
        "inprop": "url",
        "format": "json",
    }
    return _parse_search_response(_query_search(params, _retries))


if __name__ == "__main__":
    for page in wikipedia_search("quantum entanglement", max_results=3):
        print(page["title"])
        print(" ", page["url"])
        print(" ", page["summary"][:150] + "...")
        print()
