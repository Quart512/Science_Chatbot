# =========================================================
# 논문의 불변 식별자(paper_id)를 계산하는 순수 함수. LLM을 전혀 쓰지 않는다 —
# DOI/arXiv id는 등록 시점에 사용자 입력이나 arxiv_api.py의 arxiv_search()가 이미
# 구조화된 값으로 주므로, "본문을 읽고 판단"할 이유가 없는 결정론적 계산이다.
#
# 우선순위: DOI > arXiv id > 파일 내용 해시. 이 값은 논문 VDB 청크 id
# (`{paper_id}-{i}`)와 논문 카탈로그의 기본 키로 쓰이므로, 같은 논문을 다시
# 등록해도 항상 같은 값이 나와야 한다(멱등성) — 안 그러면 재등록이 중복 레코드를
# 만들거나 기존 청크가 고아로 남는다.
# =========================================================

import hashlib
import re

_DOI_URL_RE = re.compile(r"^https?://(dx\.)?doi\.org/", re.IGNORECASE)
_DOI_SCHEME_RE = re.compile(r"^doi:", re.IGNORECASE)
_ARXIV_SCHEME_RE = re.compile(r"^arxiv:", re.IGNORECASE)
_ARXIV_VERSION_RE = re.compile(r"v\d+$", re.IGNORECASE)


def _clean_doi(raw: str) -> str:
    # DOI는 대소문자를 구분하지 않는다(공식 사양) — 소문자로 통일해야 같은 DOI가
    # "10.1234/ABC"와 "10.1234/abc"로 서로 다른 논문인 것처럼 중복 등록되지 않는다.
    # "https://doi.org/..." 형태로 붙여넣는 경우가 흔해서 URL 접두사도 벗겨낸다.
    s = raw.strip()
    s = _DOI_URL_RE.sub("", s)
    s = _DOI_SCHEME_RE.sub("", s)
    return s.strip("/").lower()


def _clean_arxiv_id(raw: str) -> str:
    # 버전 접미사(v1, v2, ...)를 제거한다 — 안 그러면 논문 갱신본(v2)을 등록할 때
    # v1과 다른 논문으로 취급되어 중복 레코드가 생긴다. 우리가 원하는 건 "같은
    # 논문의 다른 버전"이지 "다른 논문"이 아니다.
    s = raw.strip()
    s = _ARXIV_SCHEME_RE.sub("", s)
    s = _ARXIV_VERSION_RE.sub("", s)
    return s.lower()


def normalize_paper_id(
    doi: str | None = None,
    arxiv_id: str | None = None,
    file_bytes: bytes | None = None,
) -> str:
    """paper_id를 우선순위대로 계산한다: DOI > arXiv id > 파일 내용 해시.

    file_bytes는 반드시 원본 파일 바이트여야 한다 — pdf_parse.py가 추출한
    텍스트가 아니다. PDF 파서를 pypdfium2 등으로 교체하거나(라이선스 문제로
    실제로 예정된 경로 — RoadMap "PDF 파싱 라이브러리 선택" 참고) 버전만
    올려도 추출된 텍스트는 미세하게 달라질 수 있는데, 텍스트를 해시하면 그때마다
    paper_id가 바뀌어 카탈로그 레코드가 고아가 된다. 파일 바이트는 파서 선택과
    무관하게 고정이므로 이 위험이 없다.

    doi, arxiv_id, file_bytes가 전부 없으면 계산할 수 없으므로 ValueError.
    """
    if doi:
        return f"doi:{_clean_doi(doi)}"

    if arxiv_id:
        return f"arxiv:{_clean_arxiv_id(arxiv_id)}"

    if file_bytes:
        digest = hashlib.sha256(file_bytes).hexdigest()
        return f"hash:{digest}"

    raise ValueError("doi, arxiv_id, file_bytes 중 최소 하나는 있어야 paper_id를 계산할 수 있다")
