# arxiv 공식 export API(https://export.arxiv.org/api/query, Atom XML)를 requests로 직접
# 호출·파싱한다 — langchain_community의 ArxivQueryRun이 막혀 있어(tool.py 참고) 새
# 의존성 없이 구조화된 서지정보(제목/저자/연도/id 등)를 얻으려고 만들었다.
# tool.py(QA)와 paper/(논문 분석기) 양쪽이 이 모듈을 공유한다.

import time
import xml.etree.ElementTree as ET

import requests

ARXIV_API_URL = "https://export.arxiv.org/api/query"  # http로 요청하면 https로 리다이렉트되며 지연 추가됨 — 처음부터 https
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"  # journal_ref/doi 등 arxiv 전용 확장 필드의 네임스페이스
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
    """arxiv API의 Atom XML 응답을 구조화된 메타데이터 리스트로 변환한다(네트워크
    호출과 분리 — 실제 API 없이 pytest 가능).

    반환 키: title, authors(list[str]), year, arxiv_id, abstract, pdf_url,
    journal_ref, doi. 이름을 summary가 아니라 abstract로 둔 이유: paper_ingest.py가
    저장하는 doc_type="summary"(LLM 생성 요약)와 헷갈리지 않게 원문 초록은 abstract로
    구분한다.

    journal_ref/doi는 기본 Atom 네임스페이스가 아니라 arxiv 전용 네임스페이스
    (ARXIV_NS) 아래 있다. preprint 단계엔 대부분 빈 문자열 — "아직 모름"이지
    "미출판"으로 단정하지 않는다(②b 스크리닝이 peer-review 신호로 구분해서 씀).
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

        journal_ref = " ".join(entry.findtext(f"{ARXIV_NS}journal_ref", default="").split())
        doi = entry.findtext(f"{ARXIV_NS}doi", default="").strip()

        results.append({
            "title": title,
            "authors": authors,
            "year": year,
            "arxiv_id": arxiv_id,
            "abstract": abstract,
            "pdf_url": pdf_url,
            "journal_ref": journal_ref,
            "doi": doi,
        })
    return results


def _query_atom(params: dict, _retries: int = 1) -> str:
    """arxiv API에 요청을 보내고(스로틀·429/503 재시도 포함) 원문 Atom XML을 반환한다.
    arxiv_search()/fetch_by_id()가 파라미터만 다르고 요청·재시도 로직은 같아 공용으로 뺐다."""
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


def arxiv_search(query: str, max_results: int = 5, start: int = 0, _retries: int = 1) -> list[dict]:
    """arxiv 논문을 검색해 구조화된 메타데이터 리스트로 반환한다(반환 키는
    _parse_atom_response 참고).

    start: arXiv API의 페이지네이션 오프셋을 그대로 노출 — 이전까지 받은 개수만큼
    올려 호출하면 다음 순위 후보를 이어서 받는다(같은 쿼리는 정렬이 안정적이라는 전제).
    """
    params = {
        "search_query": f"all:{query}",
        "start": start,
        "max_results": max_results,
    }
    return _parse_atom_response(_query_atom(params, _retries))


def fetch_by_id(arxiv_id: str, _retries: int = 1) -> dict | None:
    """arxiv id로 정확히 그 논문 하나를 조회한다(검색이 아니라 id_list 조회) — 이미
    정확한 id를 아는데 키워드 검색을 쓰면 다른 논문이 걸릴 위험이 있어 분리했다
    (register_paper()의 서지정보 자동 조회가 사용). 존재하지 않는 id면 None."""
    params = {"id_list": arxiv_id, "start": 0, "max_results": 1}
    results = _parse_atom_response(_query_atom(params, _retries))
    return results[0] if results else None


if __name__ == "__main__":
    for paper in arxiv_search("quantum entanglement", max_results=3):
        print(paper["title"], f"({paper['year']})", paper["arxiv_id"])
        print("  저자:", ", ".join(paper["authors"]))
        print("  요약:", paper["abstract"][:150] + "...")
        print()
