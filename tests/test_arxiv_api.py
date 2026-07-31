# arxiv_api.py의 XML 파싱 톨게이트 테스트 — 네트워크 호출(arxiv_search) 없이
# _parse_atom_response()만 검증. arxiv 응답 포맷이 바뀌거나 파싱 로직이 깨지면 여기서 잡힘.
# (실제 API 호출은 rate limit이 있어 CI/로컬 양쪽에서 부적절 — conftest.py의 무거운 로딩 차단과
#  같은 이유로, 이 테스트도 "외부 의존성 없이 1~2초 안에 끝나야 한다"는 톨게이트 원칙을 따름)

import arxiv_api
from arxiv_api import _parse_atom_response, fetch_by_id

SAMPLE_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.00001v2</id>
    <updated>2023-01-05T00:00:00Z</updated>
    <published>2023-01-01T00:00:00Z</published>
    <title>Quantum Entanglement in Many-Body Systems: A Review</title>
    <summary>
      We review recent progress on quantum entanglement in many-body
      systems, covering both theoretical frameworks and experimental
      realizations.
    </summary>
    <author><name>Jane Doe</name></author>
    <author><name>John Smith</name></author>
    <link href="http://arxiv.org/abs/2301.00001v2" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2301.00001v2" rel="related" type="application/pdf"/>
  </entry>
</feed>
"""

# journal_ref/doi가 있는 게재된 논문 응답(07-31) — 실제 arxiv API 응답으로 네임스페이스·
# 필드 형태 확인 후 작성. arxiv:journal_ref/arxiv:doi는 기본 Atom 네임스페이스가 아니라
# xmlns:arxiv 네임스페이스 아래 있다(arxiv_api.py의 ARXIV_NS 주석 참고).
PUBLISHED_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2111.08018v2</id>
    <published>2021-11-15T19:00:01Z</published>
    <title>Entanglement dynamics in hybrid quantum circuits</title>
    <summary>A review of entanglement dynamics.</summary>
    <author><name>Andrew C. Potter</name></author>
    <link title="pdf" href="https://arxiv.org/pdf/2111.08018v2" rel="related" type="application/pdf"/>
    <arxiv:journal_ref>Chapter in "Entanglement in Spin Chains", Springer (2022)</arxiv:journal_ref>
    <arxiv:doi>10.1007/978-3-031-03998-0_9</arxiv:doi>
  </entry>
</feed>
"""

EMPTY_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>
"""


def test_parses_single_entry():
    papers = _parse_atom_response(SAMPLE_ATOM_XML)
    assert len(papers) == 1
    p = papers[0]
    assert p["title"] == "Quantum Entanglement in Many-Body Systems: A Review"
    assert p["authors"] == ["Jane Doe", "John Smith"]
    assert p["year"] == "2023"
    assert p["arxiv_id"] == "2301.00001v2"  # 버전 접미사(v2)까지 그대로 유지
    assert p["pdf_url"] == "http://arxiv.org/pdf/2301.00001v2"
    assert "many-body" in p["abstract"]


def test_preprint_without_journal_ref_or_doi_returns_empty_strings():
    # preprint 단계(대부분)에는 journal_ref/doi가 없다 — 빈 문자열이어야지 KeyError나
    # None이 나오면 안 됨(②b 스크리닝이 "출판 안 됨"과 "필드 자체가 없음"을 구분 못 하면 곤란)
    papers = _parse_atom_response(SAMPLE_ATOM_XML)
    assert papers[0]["journal_ref"] == ""
    assert papers[0]["doi"] == ""


def test_published_entry_parses_journal_ref_and_doi():
    papers = _parse_atom_response(PUBLISHED_ATOM_XML)
    assert len(papers) == 1
    p = papers[0]
    assert "Springer" in p["journal_ref"]
    assert p["doi"] == "10.1007/978-3-031-03998-0_9"


def test_abstract_whitespace_normalized():
    # arxiv abstract는 원문에 줄바꿈·들여쓰기가 그대로 들어있음 — 한 줄로 정규화돼야 함
    papers = _parse_atom_response(SAMPLE_ATOM_XML)
    assert "\n" not in papers[0]["abstract"]


def test_empty_feed_returns_empty_list():
    assert _parse_atom_response(EMPTY_ATOM_XML) == []


# --- fetch_by_id() (07-29, register_paper() 자동 서지정보 조회용) -----------
# _query_atom()(실제 네트워크 호출)을 monkeypatch로 갈아끼워 파싱·분기 로직만 검증.


def test_fetch_by_id_returns_single_dict(monkeypatch):
    monkeypatch.setattr(arxiv_api, "_query_atom", lambda params, _retries=1: SAMPLE_ATOM_XML)
    result = fetch_by_id("2301.00001")
    assert result["title"] == "Quantum Entanglement in Many-Body Systems: A Review"


def test_fetch_by_id_returns_none_when_not_found(monkeypatch):
    monkeypatch.setattr(arxiv_api, "_query_atom", lambda params, _retries=1: EMPTY_ATOM_XML)
    assert fetch_by_id("no-such-id") is None


def test_fetch_by_id_queries_by_id_list_not_keyword_search(monkeypatch):
    # 키워드 검색(search_query)이면 제목이 비슷한 다른 논문이 걸릴 위험이 있다 — 이미 아는
    # arxiv_id를 정확히 조회하는 id_list를 써야 한다(arxiv_api.py 모듈 docstring 참고).
    captured = {}

    def _fake_query(params, _retries=1):
        captured.update(params)
        return SAMPLE_ATOM_XML

    monkeypatch.setattr(arxiv_api, "_query_atom", _fake_query)
    fetch_by_id("2301.00001")

    assert captured["id_list"] == "2301.00001"
    assert "search_query" not in captured
