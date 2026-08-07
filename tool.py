import re
from pathlib import Path

from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import StructuredTool

from arxiv_api import arxiv_search  # langchain_community의 ArxivQueryRun 대신 직접 구현(arxiv_api.py 참고)
from wikipedia_api import wikipedia_search  # DDG site 제한 검색(스니펫만 주던 임시방편) 대신 직접 구현


# wikipedia_search()의 구조화된 결과를 ToolMessage용 문자열로 펼친다 — search_arxiv와 같은 패턴.
def search_wikipedia(query: str) -> str:
    pages = wikipedia_search(query, max_results=3)
    if not pages:
        return "[결과 없음] 위키피디아에서 관련 문서를 찾지 못했다."
    return "\n\n".join(f"제목: {p['title']}\nURL: {p['url']}\n요약: {p['summary']}" for p in pages)

wikipedia_tool = StructuredTool.from_function(
    func=search_wikipedia,
    name="search_wikipedia",
    description="위키피디아에서 검색 — 제목/URL/요약을 구조화해서 반환",
)


# arxiv_search()의 구조화된 결과를 ToolMessage용 문자열로 펼친다(dict 원본은 논문
# 분석기 쪽이 별도로 그대로 씀).
def search_arxiv(query: str) -> str:
    papers = arxiv_search(query, max_results=5)
    if not papers:
        return "[결과 없음] arxiv에서 관련 논문을 찾지 못했다."
    return "\n\n".join(
        f"제목: {p['title']} ({p['year']})\n"
        f"저자: {', '.join(p['authors'])}\n"
        f"arxiv id: {p['arxiv_id']}\n"
        f"요약: {p['abstract']}"
        for p in papers
    )

arxiv_tool = StructuredTool.from_function(
    func=search_arxiv,
    name="search_arxiv",
    description="arXiv 논문 검색 — 제목/저자/연도/arxiv id/요약을 구조화해서 반환",
)

# 사용법 가이드(RoadMap "사용법 가이드 README + QA 연결" 항목) — docs/USAGE.md를 그대로
# 정본으로 쓰고 이 tool은 "## " 제목 단위로 잘라 필요한 절만 돌려준다. 전문(약 12000자)을
# 통째로 반환하면 run_tools의 4000자 캡(graph.py의 _invoke_tool_with_timeout)에 걸려
# 뒤쪽 절(연구 워크플로우·문제 해결 등)이 통째로 잘려나가므로, 절 단위 발췌가 필수다.
# 요약을 따로 하드코딩하지 않은 이유: 사용법이 바뀔 때마다 문서·요약 두 곳을 맞춰야
# 하는 드리프트 위험을 피하고 docs/USAGE.md 하나만 정본으로 유지하기 위함.
USAGE_GUIDE_PATH = Path(__file__).parent / "docs" / "USAGE.md"


def _parse_usage_sections() -> dict[str, str]:
    text = USAGE_GUIDE_PATH.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^## ", text)[1:]  # [0]은 "## " 이전의 문서 제목·인트로
    sections = {}
    for part in parts:
        heading, _, body = part.partition("\n")
        sections[heading.strip()] = body.strip()
    return sections


# topic은 자유 텍스트 — LLM이 "관심사", "논문 등록", "연구 워크플로우"처럼 대충 골라
# 불러도 정확한 절 제목과 부분 일치(대소문자 무시)로 찾는다. 못 찾으면 실제 절 제목
# 목록을 돌려줘서 LLM이 다음 라운드에 정확한 이름으로 재호출할 수 있게 한다
# (search_wikipedia/search_arxiv의 "[결과 없음]" 패턴과 동일).
def read_usage_guide(topic: str) -> str:
    sections = _parse_usage_sections()
    if topic in sections:
        return sections[topic]
    lowered = topic.lower()
    for heading, body in sections.items():
        if lowered in heading.lower() or heading.lower() in lowered:
            return body
    return "[찾을 수 없음] 사용 가능한 항목: " + ", ".join(sections.keys())


usage_guide_tool = StructuredTool.from_function(
    func=read_usage_guide,
    name="read_usage_guide",
    description=(
        "AIsaac 앱 자체의 사용법을 묻거나, 챗봇이 직접 실행할 수 없는 앱 내 동작(관심사 "
        "등록 등)을 요청받았을 때 사용 — 물리 지식 질문에는 쓰지 않는다. topic에 화면/기능 "
        "이름(예: '관심사', '논문 등록', "
        "'연구 워크플로우', '실험도구', 'API 키')을 넣어 호출."
    ),
)

tools_list = [DuckDuckGoSearchRun(description="일반 범용성 검색"),
        arxiv_tool,
        wikipedia_tool,
        usage_guide_tool,
        ]
tool_map = {tool.name: tool for tool in tools_list} #이름으로 검색할 수 있게