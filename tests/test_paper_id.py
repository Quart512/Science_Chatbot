"""
normalize_paper_id — paper_id.py의 순수 함수. LLM·네트워크·VDB 없이 1초 안에 도는
톨게이트 테스트. 검증 대상: 우선순위(DOI > arxiv > 해시), 입력 누락 조합, 해시
안정성, DOI/arXiv 정규화(대소문자·접두사·버전 접미사).
"""
import pytest

from paper_id import normalize_paper_id


def test_doi_has_highest_priority():
    result = normalize_paper_id(doi="10.1234/abc", arxiv_id="2401.12345", file_bytes=b"pdf-bytes")
    assert result == "doi:10.1234/abc"


def test_arxiv_used_when_no_doi():
    result = normalize_paper_id(doi=None, arxiv_id="2401.12345", file_bytes=b"pdf-bytes")
    assert result == "arxiv:2401.12345"


def test_hash_used_when_no_doi_or_arxiv():
    result = normalize_paper_id(doi=None, arxiv_id=None, file_bytes=b"pdf-bytes")
    assert result.startswith("hash:")


def test_raises_when_all_inputs_missing():
    with pytest.raises(ValueError):
        normalize_paper_id(doi=None, arxiv_id=None, file_bytes=None)


def test_doi_lowercased():
    assert normalize_paper_id(doi="10.1234/ABC-XYZ") == "doi:10.1234/abc-xyz"


def test_doi_strips_url_prefix():
    assert normalize_paper_id(doi="https://doi.org/10.1234/abc") == "doi:10.1234/abc"
    assert normalize_paper_id(doi="http://dx.doi.org/10.1234/abc") == "doi:10.1234/abc"


def test_doi_strips_existing_scheme_prefix():
    assert normalize_paper_id(doi="doi:10.1234/abc") == "doi:10.1234/abc"


def test_arxiv_version_suffix_stripped():
    # v1과 v2는 같은 논문의 다른 버전 — 같은 paper_id로 매칭돼야 갱신본 등록이
    # 중복 레코드를 만들지 않는다
    v1 = normalize_paper_id(arxiv_id="2401.12345v1")
    v2 = normalize_paper_id(arxiv_id="2401.12345v2")
    assert v1 == v2 == "arxiv:2401.12345"


def test_arxiv_lowercased_and_scheme_stripped():
    assert normalize_paper_id(arxiv_id="arXiv:2401.12345") == "arxiv:2401.12345"


def test_hash_is_stable_for_same_bytes():
    # 카탈로그 기본 키로 쓰이므로(같은 논문 재등록 시 같은 id가 나와야 함) 이 멱등성이
    # 핵심 — "다른 바이트면 다른 해시"는 SHA-256 자체의 성질이라 별도로 안 테스트함
    a = normalize_paper_id(file_bytes=b"same content")
    b = normalize_paper_id(file_bytes=b"same content")
    assert a == b
