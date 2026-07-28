"""
retrieve() — graph.py의 검색 노드. feynman(물리 강의록) 컬렉션과 papers_vectorstore(②a
논문 라이브러리) 컬렉션을 같은 질문으로 둘 다 검색해 합치는지, 그리고 요약이 없는 논문을
발견하면 paper_ingest.ensure_summary_in_background()를 트리거하는지 확인하는 톨게이트
테스트. conftest.py가 안내하는 대로 graph.vectorstore/graph.papers_vectorstore를
monkeypatch로 갈아끼운다 — 진짜 Chroma·임베딩 모델은 전혀 안 건드림.
"""
import paper_ingest
import pytest
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


@pytest.fixture(autouse=True)
def _stub_background_summary(monkeypatch):
    # retrieve()는 논문 청크를 보면 paper_ingest.ensure_summary_in_background()를 부른다 —
    # 이 파일의 대부분 테스트는 "문서 병합" 로직만 보면 되므로 기본은 아무 일도 안 하는
    # 가짜로 갈아끼운다. ensure_summary_in_background() 자체의 판단 로직(캐시 확인·중복
    # 방지)은 tests/test_paper_ingest.py에서 따로 검증한다. 아래 트리거 전용 테스트들은
    # 이 스텁을 스파이로 다시 덮어써서 호출 여부·인자를 직접 확인한다.
    monkeypatch.setattr(paper_ingest, "ensure_summary_in_background", lambda *a, **kw: False)


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


def test_retrieve_triggers_background_summary_for_papers_missing_it(monkeypatch, make_state):
    paper_docs = [Document(page_content="논문 청크", metadata={"paper_id": "arxiv:missing", "doc_type": "fulltext_chunk"})]
    monkeypatch.setattr("graph.vectorstore", _FakeVectorstore([]))
    monkeypatch.setattr("graph.papers_vectorstore", _FakeVectorstore(paper_docs))

    calls = []
    def _spy(paper_id, **kwargs):
        calls.append(paper_id)
        return True
    monkeypatch.setattr(paper_ingest, "ensure_summary_in_background", _spy)

    result = retrieve(make_state())

    assert calls == ["arxiv:missing"]
    assert "백그라운드로 시작함" in result["trace"]


def test_retrieve_skips_background_summary_when_only_summary_docs_found(monkeypatch, make_state):
    # doc_type이 이미 summary인 문서만 검색됐다는 건 그 논문 요약이 이미 있다는 뜻 —
    # fulltext_chunk가 아니므로 애초에 백그라운드 생성 후보에 안 들어가야 한다
    paper_docs = [Document(page_content="요약", metadata={"paper_id": "arxiv:has-summary", "doc_type": "summary"})]
    monkeypatch.setattr("graph.vectorstore", _FakeVectorstore([]))
    monkeypatch.setattr("graph.papers_vectorstore", _FakeVectorstore(paper_docs))

    calls = []
    monkeypatch.setattr(paper_ingest, "ensure_summary_in_background", lambda pid, **kw: calls.append(pid))

    result = retrieve(make_state())

    assert calls == []
    assert "백그라운드로 시작함" not in result["trace"]
