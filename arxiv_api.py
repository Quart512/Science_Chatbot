# =========================================================
# arxiv 공식 API(export.arxiv.org)를 직접 호출해 구조화된 논문 메타데이터를 가져오는 모듈.
#
# 기존 langchain_community의 ArxivQueryRun은 arxiv.org 서버 자체 이슈(2025-11 이후)와
# langchain_community 쪽의 구버전 API 요구사항이 겹쳐 막혀있었다(tool.py 주석 참고).
# 그 우회책으로 DuckDuckGo에 site:arxiv.org를 붙여 검색해왔는데, 이건 검색 스니펫만 줄 뿐
# 제목/저자/연도/arxiv id 같은 구조화된 서지정보는 못 준다.
#
# 이 모듈은 langchain_community 래퍼를 거치지 않고 arxiv의 export API
# (https://export.arxiv.org/api/query, Atom XML)를 requests로 직접 호출·파싱한다.
# 새 의존성 추가 없이(표준 라이브러리 xml + 이미 쓰던 requests) 구조화된 결과를 얻는다.
#
# 두 곳에서 재사용됨:
#   - tool.py: 물리 QA 능력의 tool-calling 루프에서 쓰는 "arxiv 논문 검색" tool
#   - (예정) 6-3 논문 분석기: abstract 트리아지 단계가 이 구조화된 메타데이터를 그대로 소비
#     (서지정보가 이미 갖춰져 있어야 인용 포맷(BibTeX 등)을 만들 수 있음)
# =========================================================

import time
import xml.etree.ElementTree as ET

import requests

ARXIV_API_URL = "https://export.arxiv.org/api/query"  # http로 요청하면 https로 리다이렉트되며 지연 추가됨 — 처음부터 https
ATOM_NS = "{http://www.w3.org/2005/Atom}"
# arxiv는 정체를 알 수 없는 요청(기본 python-requests User-Agent 등)에 응답을 지연시키는 경우가 있어 명시
HEADERS = {"User-Agent": "Science_Chatbot/0.1 (student project; contact: d3725gt@gmail.com)"}

# arxiv 공식 가이드라인: 3초에 한 번 이상 요청하지 말 것 (실측: 짧은 간격 연속 호출 시 429 "Rate exceeded")
MIN_INTERVAL_SEC = 3.0
_last_request_at = 0.0


def _throttle():
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < MIN_INTERVAL_SEC:
        time.sleep(MIN_INTERVAL_SEC - elapsed)
    _last_request_at = time.monotonic()


def _parse_atom_response(xml_text: str) -> list[dict]:
    """arxiv API의 Atom XML 응답을 파싱해 구조화된 메타데이터 리스트로 변환.

    네트워크(requests) 호출과 분리해둔 이유: 이 부분만 순수 함수로 떼어놔야
    실제 API를 안 두드리고도(=arxiv rate limit 걱정 없이) pytest로 검증할 수 있음.
    각 항목의 키: title, authors(list[str]), year, arxiv_id, abstract, pdf_url

    키 이름이 summary가 아니라 abstract인 이유(07-28): paper_ingest.py가 Chroma에
    저장하는 doc_type="summary"(우리가 LLM으로 만든 구조화 요약)와 이름이 겹치면
    "이 논문의 abstract"와 "우리가 생성한 요약"을 코드에서 헷갈리기 쉽다 — 이건
    저자가 쓴 원문 그대로의 초록이라 abstract로 구분한다.
    """
    root = ET.fromstring(xml_text)
    results = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        title = " ".join(entry.findtext(f"{ATOM_NS}title", default="").split())
        abstract = " ".join(entry.findtext(f"{ATOM_NS}summary", default="").split())
        published = entry.findtext(f"{ATOM_NS}published", default="")
        year = published[:4] if published else ""

        # id는 "http://arxiv.org/abs/2301.00001v1" 형태 — 마지막 조각이 버전 포함 arxiv id
        arxiv_url = entry.findtext(f"{ATOM_NS}id", default="")
        arxiv_id = arxiv_url.rsplit("/", 1)[-1] if arxiv_url else ""

        authors = [
            " ".join(a.findtext(f"{ATOM_NS}name", default="").split())
            for a in entry.findall(f"{ATOM_NS}author")
        ]

        pdf_url = ""
        for link in entry.findall(f"{ATOM_NS}link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", "")
                break

        results.append({
            "title": title,
            "authors": authors,
            "year": year,
            "arxiv_id": arxiv_id,
            "abstract": abstract,
            "pdf_url": pdf_url,
        })
    return results


def _query_atom(params: dict, _retries: int = 1) -> str:
    """arxiv API에 실제 요청을 보내고(스로틀·429/503 재시도 포함) 원문 Atom XML을
    반환한다. arxiv_search()(키워드 검색, search_query)와 fetch_by_id()(정확한 id 조회,
    id_list)가 파라미터만 다르고 요청·재시도 로직은 완전히 같아서 공용으로 뺐다(07-29)."""
    for attempt in range(_retries + 1):
        _throttle()
        try:
            resp = requests.get(ARXIV_API_URL, params=params, headers=HEADERS, timeout=10)
        except requests.exceptions.RequestException:
            # ReadTimeout/ConnectionError 등은 상태 코드를 받기도 전에 나는 예외라 아래
            # status_code 체크로는 못 잡음 — 429/503과 똑같이 재시도 대상으로 취급
            if attempt < _retries:
                time.sleep(MIN_INTERVAL_SEC * 2)
                continue
            raise
        # 429(요청 과다)와 503(arxiv 공식 문서에 나오는 "서버 과부하 — Retry-After 존중" 응답) 둘 다 재시도
        if resp.status_code in (429, 503) and attempt < _retries:
            wait = float(resp.headers.get("Retry-After", 0)) or MIN_INTERVAL_SEC * 2
            time.sleep(max(wait, 1.0))  # Retry-After: 0이어도 최소 1초는 텀을 둠
            continue
        resp.raise_for_status()
        break

    return resp.text


def arxiv_search(query: str, max_results: int = 5, _retries: int = 1) -> list[dict]:
    """arxiv 논문을 검색해 구조화된 메타데이터 리스트로 반환한다.

    각 항목의 키: title, authors(list[str]), year, arxiv_id, abstract, pdf_url
    """
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
    }
    return _parse_atom_response(_query_atom(params, _retries))


def fetch_by_id(arxiv_id: str, _retries: int = 1) -> dict | None:
    """arxiv id로 정확히 그 논문 하나를 조회한다(검색이 아니라 조회 — id_list 파라미터).

    arxiv_search()는 키워드 검색이라 제목 등으로 찾으면 다른 논문이 걸릴 위험이 있는데,
    이미 정확한 arxiv_id를 알고 있을 때는 이렇게 조회하는 게 맞다(paper_ingest.py의
    register_paper()가 등록 시 bibliographic을 자동으로 채울 때 씀, 07-29).

    반환 키는 arxiv_search()와 동일: title, authors, year, arxiv_id, abstract, pdf_url.
    존재하지 않는 id(오타 등)면 None.
    """
    params = {"id_list": arxiv_id, "start": 0, "max_results": 1}
    results = _parse_atom_response(_query_atom(params, _retries))
    return results[0] if results else None


if __name__ == "__main__":
    for paper in arxiv_search("quantum entanglement", max_results=3):
        print(paper["title"], f"({paper['year']})", paper["arxiv_id"])
        print("  저자:", ", ".join(paper["authors"]))
        print("  요약:", paper["abstract"][:150] + "...")
        print()
