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

tools_list = [DuckDuckGoSearchRun(description="일반 범용성 검색"),
        arxiv_tool,
        wikipedia_tool,
        ]
tool_map = {tool.name: tool for tool in tools_list} #이름으로 검색할 수 있게