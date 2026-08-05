# read_usage_guide (tool.py) — docs/USAGE.md를 "## " 절 단위로 잘라 반환하는 순수
# 함수. 네트워크·LLM 없이 실제 파일을 읽어 검증(파싱 로직 자체가 대상이라 가짜 파일로
# 대체하면 검증 의미가 옅어짐 — arxiv_api 테스트가 파싱은 실제 포맷으로, 네트워크만
# monkeypatch하는 것과 같은 결).

from tool import _parse_usage_sections, read_usage_guide


def test_parse_usage_sections_returns_known_headings():
    sections = _parse_usage_sections()
    assert "연구 워크플로우로 연구 진행하기" in sections
    assert "API 키 설정" in sections
    assert all(body.strip() for body in sections.values())


def test_read_usage_guide_exact_heading_match():
    result = read_usage_guide("API 키 설정")
    assert "Gemini" in result


def test_read_usage_guide_partial_match_is_case_insensitive():
    result = read_usage_guide("관심사")
    assert "지금 검색" in result


def test_read_usage_guide_unknown_topic_lists_available_headings():
    result = read_usage_guide("존재하지 않는 화면")
    assert result.startswith("[찾을 수 없음]")
    assert "API 키 설정" in result


# run_tools()의 _invoke_tool_with_timeout()가 결과를 4000자로 자른다(graph.py) — 절이
# 그 한도를 넘으면 뒷부분이 조용히 잘려나간다. 앞으로 USAGE.md가 늘어나도 이 한도를
# 넘는 절이 생기면 여기서 바로 드러나게 하는 회귀 가드.
def test_all_sections_fit_within_tool_result_cap():
    TOOL_RESULT_CAP = 4000
    sections = _parse_usage_sections()
    for heading, body in sections.items():
        assert len(body) < TOOL_RESULT_CAP, f"'{heading}' 절이 {len(body)}자 — 4000자 캡에 잘림"
