from langchain_community.tools import DuckDuckGoSearchRun
#import wikipedia
#wikipedia.set_user_agent("KTB4-jimmy-AI-feynman-agent/0.1 (student project)")
#from langchain_community.tools import WikipediaQueryRun  #user_agent 설정해도 JSONDecodeError 재현됨 (search는 성공하지만 무관한 결과 반환 + 특정 페이지 fetch에서 크래시) — wikipedia 패키지 자체가 신뢰 못 할 수준. wikipedia-api 기반 커스텀 tool 필요 (나중에)
#from langchain_community.utilities import WikipediaAPIWrapper
#from langchain_community.tools.arxiv.tool import ArxivQueryRun
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_core.tools import StructuredTool

from typing import NamedTuple

class SiteConfig(NamedTuple): # 수정 불가능하게+3개 변수 딕셔너리에
    domain: str
    description: str

ddg_sites_map = {
    "wikipedia": SiteConfig("en.wikipedia.org", "위키피디아에서 검색"),
    "arxiv": SiteConfig("arxiv.org", "arXiv 논문 검색"),
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

#bind tools
tools_list = [DuckDuckGoSearchRun(description="일반 범용성 검색"),
        #WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper()), #user_agent 설정해도 JSONDecodeError — wikipedia 패키지 자체 신뢰성 문제, 커스텀 tool 필요
        #ArxivQueryRun(),  #arxiv.org 서버 자체 이슈 (2025-11 이후), langchain_community도 구버전 API 요구
        *site_tools
        ]
tool_map = {tool.name: tool for tool in tools_list} #이름으로 검색할 수 있게