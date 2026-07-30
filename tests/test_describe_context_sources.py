"""
describe_context_sources() — graph.py의 순수 함수(07-29, 답변 근거 표시 작업). state.context의
Document 메타데이터만 보고 "이번 턴에 참고할 수 있었던 자료"를 사람이 읽을 문자열로 정리한다.
LLM 호출 없음 — 결정론적 포매팅만 검증하는 톨게이트 테스트.
"""
from langchain_core.documents import Document

from graph import describe_context_sources


def test_describe_context_sources_lists_feynman():
    docs = [Document(page_content="x", metadata={"source": "feynman"})]
    assert "파인만 강의록" in describe_context_sources(docs)


def test_describe_context_sources_shows_paper_title_and_doc_type():
    docs = [Document(
        page_content="x",
        metadata={"paper_id": "arxiv:1", "doc_type": "fulltext_chunk", "title": "테스트 논문"},
    )]
    result = describe_context_sources(docs)
    assert "테스트 논문" in result
    assert "전문 발췌" in result


def test_describe_context_sources_falls_back_to_paper_id_without_title():
    # summary/abstract 문서처럼 title 메타데이터가 없으면 paper_id를 그대로 보여준다
    # (register_paper()의 "abstract 확보" 주석 참고 — summary는 아직 title을 못 붙임)
    docs = [Document(page_content="x", metadata={"paper_id": "arxiv:no-title", "doc_type": "summary"})]
    assert "arxiv:no-title" in describe_context_sources(docs)


def test_describe_context_sources_merges_doc_types_for_same_paper():
    # 같은 논문의 전문 청크와 요약이 둘 다 검색되면 한 줄에 doc_type을 모아서 보여준다
    docs = [
        Document(page_content="x", metadata={"paper_id": "arxiv:1", "doc_type": "fulltext_chunk", "title": "논문A"}),
        Document(page_content="y", metadata={"paper_id": "arxiv:1", "doc_type": "summary"}),
    ]
    result = describe_context_sources(docs)
    assert result.count("논문A") == 1  # 두 줄이 아니라 한 줄로 합쳐짐
    assert "전문 발췌" in result and "요약" in result


def test_describe_context_sources_lists_tool_results_without_duplicates():
    docs = [
        Document(page_content="x", metadata={"source": "search_arxiv"}),
        Document(page_content="y", metadata={"source": "search_arxiv"}),  # 같은 tool 두 번 호출
    ]
    result = describe_context_sources(docs)
    assert result.count("search_arxiv") == 1


def test_describe_context_sources_empty_context_returns_empty_string():
    assert describe_context_sources([]) == ""
