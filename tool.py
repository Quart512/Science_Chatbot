from langchain_community.tools import DuckDuckGoSearchRun
#import wikipedia
#wikipedia.set_user_agent("KTB4-jimmy-AI-feynman-agent/0.1 (student project)")
#from langchain_community.tools import WikipediaQueryRun  #user_agent 설정해도 JSONDecodeError 재현됨 (search는 성공하지만 무관한 결과 반환 + 특정 페이지 fetch에서 크래시) — wikipedia 패키지 자체가 신뢰 못 할 수준. wikipedia-api 기반 커스텀 tool 필요 (나중에)
#from langchain_community.utilities import WikipediaAPIWrapper
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_core.tools import StructuredTool

from typing import NamedTuple

from arxiv_api import arxiv_search  # langchain_community의 ArxivQueryRun(막혀있었음) 대신 직접 구현

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


# arxiv 논문 검색 tool. arxiv_search()가 주는 구조화된 결과(제목/저자/연도/id/요약)를
# LLM이 읽을 수 있는 텍스트로 펼쳐서 반환 — ToolMessage는 문자열이어야 하므로.
# 이 포맷팅은 6-3 논문 분석기가 쓸 원본 dict 구조(arxiv_search 반환값)와는 별개 — 거긴 dict 그대로 씀
def search_arxiv(query: str) -> str:
    papers = arxiv_search(query, max_results=5)
    if not papers:
        return "[결과 없음] arxiv에서 관련 논문을 찾지 못했다."
    return "\n\n".join(
        f"제목: {p['title']} ({p['year']})\n"
        f"저자: {', '.join(p['authors'])}\n"
        f"arxiv id: {p['arxiv_id']}\n"
        f"요약: {p['summary']}"
        for p in papers
    )

arxiv_tool = StructuredTool.from_function(
    func=search_arxiv,
    name="search_arxiv",
    description="arXiv 논문 검색 — 제목/저자/연도/arxiv id/요약을 구조화해서 반환",
)

#bind tools
tools_list = [DuckDuckGoSearchRun(description="일반 범용성 검색"),
        #WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper()), #user_agent 설정해도 JSONDecodeError — wikipedia 패키지 자체 신뢰성 문제, 커스텀 tool 필요
        arxiv_tool,
        *site_tools
        ]
tool_map = {tool.name: tool for tool in tools_list} #이름으로 검색할 수 있게