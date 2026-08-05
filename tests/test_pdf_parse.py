"""
_extract_pdf_title() — pdf_parse.py의 제목 후보 추출(07-29, 6-3b③ 제목 검증용). 실제
PyMuPDF 문서 없이, doc.metadata만 흉내내는 가짜 객체로 순수 로직만 검증하는 톨게이트
테스트 — fitz.Document는 doc.metadata.get(...) 하나만 호출되므로 이 부분만 흉내내면 된다.
"""
from paper.pdf_parse import _extract_pdf_title


class _FakeDoc:
    def __init__(self, metadata: dict):
        self.metadata = metadata


def test_prefers_pdf_metadata_title():
    doc = _FakeDoc({"title": "PDF 메타데이터 제목"})
    assert _extract_pdf_title(doc, "# 마크다운 제목\n\n본문") == "PDF 메타데이터 제목"


def test_falls_back_to_first_markdown_line_when_metadata_empty():
    doc = _FakeDoc({"title": ""})
    assert _extract_pdf_title(doc, "## 마크다운 제목\n\n본문") == "마크다운 제목"


def test_strips_markdown_heading_and_bold_markers():
    doc = _FakeDoc({"title": ""})
    assert _extract_pdf_title(doc, "**볼드 제목**\n\n본문") == "볼드 제목"


def test_skips_blank_lines_to_find_first_content_line():
    doc = _FakeDoc({"title": ""})
    assert _extract_pdf_title(doc, "\n\n   \n제목 줄\n본문") == "제목 줄"


def test_returns_none_when_nothing_found():
    doc = _FakeDoc({"title": ""})
    assert _extract_pdf_title(doc, "") is None


def test_missing_metadata_key_does_not_crash():
    # fitz.Document.metadata는 보통 모든 표준 키를 갖고 있지만, 방어적으로 .get() 사용을
    # 확인 — dict에 title 키 자체가 없어도 죽지 않아야 함
    doc = _FakeDoc({})
    assert _extract_pdf_title(doc, "본문 제목") == "본문 제목"


# --- 08-05 라이브 검증에서 실제로 재현한 버그: 논문 유통 플랫폼이 심어놓은 슬러그성
# 메타데이터('DBPIA-NURIMEDIA', 공백 없는 한 단어)가 폴백을 막아 정확한 제목을 줘도
# classify_title_match()가 최악 등급을 냈다. -----------------------------------

def test_falls_back_to_markdown_when_metadata_has_no_space():
    doc = _FakeDoc({"title": "DBPIA-NURIMEDIA"})
    assert _extract_pdf_title(doc, "# 진짜 논문 제목\n\n본문") == "진짜 논문 제목"


def test_prefers_h1_heading_over_earlier_lower_level_heading():
    # 실제로 겪은 구조 — 저널 정보(h3)가 진짜 제목(h1)보다 먼저 나옴
    markdown = "### New Physics: Sae Mulli, Vol. 76\n\n\n\n# A performance comparison\n\n## Author Name"
    doc = _FakeDoc({"title": ""})
    assert _extract_pdf_title(doc, markdown) == "A performance comparison"


def test_uses_no_space_metadata_as_last_resort_when_markdown_empty():
    # 마크다운이 아예 없으면(스캔본 등) 공백 없는 메타데이터라도 안 주는 것보다는 낫다
    doc = _FakeDoc({"title": "DBPIA-NURIMEDIA"})
    assert _extract_pdf_title(doc, "") == "DBPIA-NURIMEDIA"
