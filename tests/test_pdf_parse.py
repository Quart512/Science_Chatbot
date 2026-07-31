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
