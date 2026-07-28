# arxiv_api.py의 XML 파싱 톨게이트 테스트 — 네트워크 호출(arxiv_search) 없이
# _parse_atom_response()만 검증. arxiv 응답 포맷이 바뀌거나 파싱 로직이 깨지면 여기서 잡힘.
# (실제 API 호출은 rate limit이 있어 CI/로컬 양쪽에서 부적절 — conftest.py의 무거운 로딩 차단과
#  같은 이유로, 이 테스트도 "외부 의존성 없이 1~2초 안에 끝나야 한다"는 톨게이트 원칙을 따름)

from arxiv_api import _parse_atom_response

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


def test_abstract_whitespace_normalized():
    # arxiv abstract는 원문에 줄바꿈·들여쓰기가 그대로 들어있음 — 한 줄로 정규화돼야 함
    papers = _parse_atom_response(SAMPLE_ATOM_XML)
    assert "\n" not in papers[0]["abstract"]


def test_empty_feed_returns_empty_list():
    assert _parse_atom_response(EMPTY_ATOM_XML) == []
