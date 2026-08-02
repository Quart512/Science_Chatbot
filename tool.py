from langchain_community.tools import DuckDuckGoSearchRun
# wikipedia 패키지는 신뢰성 문제로 배제(RoadMap "tool 정비" 참고) — wikipedia-api 기반 커스텀 tool 예정
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_core.tools import StructuredTool

from typing import NamedTuple

from arxiv_api import arxiv_search  # langchain_community의 ArxivQueryRun 대신 직접 구현(arxiv_api.py 참고)

class SiteConfig(NamedTuple): # 수정 불가능하게+3개 변수 딕셔너리에
    domain: str
    description: str

ddg_sites_map = {
    "wikipedia": SiteConfig("en.wikipedia.org", "위키피디아에서 검색"),
}
# 팩토리 — 딱 한 번만 정의
def make_search_tool(name: str, config: SiteConfig):
    def search(query: str) -> str:
        return DuckDuckGoSearchAPIWrapper().run(f"site:{config.domain} {query}")
    return StructuredTool.from_function(
        func=search,
        name=f"search_{name}",
        description=config.description,
    )
# .items()로 name과 config를 같이 꺼냄
site_tools = [make_search_tool(name, config) for name, config in ddg_sites_map.items()]


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

tools_list = [DuckDuckGoSearchRun(description="일반 범용성 검색"),
        arxiv_tool,
        *site_tools
        ]
tool_map = {tool.name: tool for tool in tools_list} #이름으로 검색할 수 있게