"""
retrieve() — graph.py의 검색 노드. feynman(물리 강의록) 컬렉션과 papers_vectorstore(②a
논문 라이브러리) 컬렉션을 같은 질문으로 둘 다 검색해 합치는지 확인하는 톨게이트 테스트.
conftest.py가 안내하는 대로 graph.vectorstore/graph.papers_vectorstore를 monkeypatch로
갈아끼운다 — 진짜 Chroma·임베딩 모델은 전혀 안 건드림.
"""
from langchain_core.documents import Document

from graph import retrieve


class _FakeRetriever:
    def __init__(self, docs):
        self.docs = docs

    def invoke(self, question):
        return self.docs


class _FakeVectorstore:
    def __init__(self, docs):
        self.docs = docs

    def as_retriever(self, search_kwargs=None):
        return _FakeRetriever(self.docs)


def test_retrieve_merges_feynman_and_paper_docs(monkeypatch, make_state):
    feynman_docs = [Document(page_content="파인만 강의록", metadata={"source": "feynman"})]
    paper_docs = [Document(page_content="논문 청크", metadata={"paper_id": "arxiv:1", "doc_type": "fulltext_chunk"})]

    monkeypatch.setattr("graph.vectorstore", _FakeVectorstore(feynman_docs))
    monkeypatch.setattr("graph.papers_vectorstore", _FakeVectorstore(paper_docs))

    result = retrieve(make_state())

    assert feynman_docs[0] in result["context"]
    assert paper_docs[0] in result["context"]


def test_retrieve_handles_empty_paper_library(monkeypatch, make_state):
    # 등록된 논문이 아직 없으면(컬렉션이 비어있으면) 빈 리스트만 돌아와야 한다 — 기존
    # feynman 전용 동작을 깨면 안 됨(eval.json 코퍼스엔 논문이 없어 이 경로가 정상 케이스)
    feynman_docs = [Document(page_content="파인만 강의록", metadata={"source": "feynman"})]

    monkeypatch.setattr("graph.vectorstore", _FakeVectorstore(feynman_docs))
    monkeypatch.setattr("graph.papers_vectorstore", _FakeVectorstore([]))

    result = retrieve(make_state())

    assert result["context"] == feynman_docs


def test_retrieve_preserves_tool_docs_alongside_paper_docs(monkeypatch, make_state):
    # tool로 수집한 문서(source가 tool_map 키)는 재검색 때도 보존돼야 한다는 기존 규칙이
    # 논문 검색 추가로 깨지지 않는지 확인
    from tool import tool_map

    tool_name = next(iter(tool_map))
    tool_doc = Document(page_content="tool 결과", metadata={"source": tool_name})
    paper_docs = [Document(page_content="논문 청크", metadata={"paper_id": "arxiv:1", "doc_type": "fulltext_chunk"})]

    monkeypatch.setattr("graph.vectorstore", _FakeVectorstore([]))
    monkeypatch.setattr("graph.papers_vectorstore", _FakeVectorstore(paper_docs))

    state = make_state(context=[tool_doc])
    result = retrieve(state)

    assert tool_doc in result["context"]
    assert paper_docs[0] in result["context"]
