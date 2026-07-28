"""
retrieve() — graph.py의 검색 노드. feynman(물리 강의록) 컬렉션과 papers_vectorstore(②a
논문 라이브러리) 컬렉션을 같은 질문으로 둘 다 검색해 유사도 점수로 병합하는지(총 문서 수가
k를 넘지 않는지 — 07-28 리뷰 반영), 그리고 요약이 없는 논문을 발견하면
paper_ingest.ensure_summary_in_background()를 트리거하는지 확인하는 톨게이트 테스트.
conftest.py가 안내하는 대로 graph.vectorstore/graph.papers_vectorstore를 monkeypatch로
갈아끼운다 — 진짜 Chroma·임베딩 모델은 전혀 안 건드림.
"""
import pytest
from langchain_core.documents import Document

from graph import retrieve
from paper import paper_ingest


class _FakeVectorstore:
    def __init__(self, docs, scores=None):
        self.docs = docs
        # scores를 안 주면 리스트 앞쪽일수록 더 유사하다(점수가 작다)고 가정한다(진짜
        # Chroma의 L2 거리를 흉내). 명시적으로 줄 수도 있게 한 이유: 두 컬렉션의 병합
        # 순서가 "어느 쪽이 리스트에 먼저 있었나"가 아니라 실제 점수로 결정돼야 하는
        # 테스트(예: 한 논문이 feynman보다 항상 점수가 좋은 경우)에서 이걸 직접 통제해야 함.
        self.scores = scores if scores is not None else [float(i) for i in range(len(docs))]

    def similarity_search_with_score(self, question, k=None):
        scored = list(zip(self.docs, self.scores))
        return scored[:k] if k is not None else scored


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


def test_retrieve_caps_total_context_at_k_via_score_merge(monkeypatch, make_state):
    # 예전엔 feynman·papers 각 컬렉션에서 k개씩 가져와 단순히 이어붙였다 — 논문이 등록된
    # 순간부터 매번 최대 2k개가 context에 들어간 버그(07-28 리뷰 지적). top_k(effort
    # 프로필의 비용 다이얼)의 원래 의도는 "컬렉션당 몇 개"가 아니라 "총 몇 개"이므로,
    # 두 컬렉션 후보를 점수로 병합한 뒤 상위 k개만 남아야 한다 — 그리고 그 k개는 한쪽
    # 컬렉션만이 아니라 점수 기준으로 실제 섞여야 한다(그냥 feynman만 우선하는 것도,
    # papers만 우선하는 것도 아님을 확인).
    feynman_docs = [Document(page_content=f"파인만 {i}", metadata={"source": "feynman"}) for i in range(3)]
    paper_docs = [
        Document(page_content=f"논문 {i}", metadata={"paper_id": f"arxiv:{i}", "doc_type": "fulltext_chunk"})
        for i in range(3)
    ]

    monkeypatch.setattr("graph.vectorstore", _FakeVectorstore(feynman_docs))
    monkeypatch.setattr("graph.papers_vectorstore", _FakeVectorstore(paper_docs))

    state = make_state(effort="medium")  # top_k=3
    result = retrieve(state)

    assert len(result["context"]) == 3  # 6개(3+3)가 아니라 k(3)개로 캡됨
    sources = {d.metadata.get("source") for d in result["context"]}
    paper_ids = {d.metadata.get("paper_id") for d in result["context"]}
    assert "feynman" in sources  # 두 컬렉션이 실제로 섞여야 함(점수 병합이지 한쪽 우선이 아님)
    assert paper_ids - {None}  # papers 쪽도 최소 하나는 살아남아야 함


def test_retrieve_caps_chunks_from_same_paper(monkeypatch, make_state):
    # 같은 논문의 summary+fulltext_chunk가 둘 다 검색되거나, split_for_embedding의
    # chunk_overlap 때문에 인접 청크가 겹치거나, 같은 주장이 여러 청크에 반복되는 등
    # 한 논문 내부 중복 원인이 여러 겹이라(07-28 리뷰 지적), 점수 병합만 하면 논문
    # 한 편이 k 슬롯을 전부 차지할 수 있다 — 같은 paper_id 청크 4개가 feynman 문서
    # 2개보다 항상 점수가 좋다고(작다고) 흉내내서, top_k(3)를 뽑을 때 그 논문
    # 청크가 2개까지만 들어가고 나머지 한 자리는 feynman으로 채워지는지 확인한다.
    feynman_docs = [Document(page_content=f"파인만 {i}", metadata={"source": "feynman"}) for i in range(2)]
    paper_docs = [
        Document(page_content=f"논문청크 {i}", metadata={"paper_id": "arxiv:mono", "doc_type": "fulltext_chunk", "index": i})
        for i in range(4)
    ]

    # paper_docs가 항상 feynman_docs보다 점수가 좋도록(값이 작도록) 명시적으로 지정 —
    # 그래야 "캡이 없었다면 이 논문 청크들이 top_k를 전부 차지했을 것"이 확실해진다.
    monkeypatch.setattr("graph.vectorstore", _FakeVectorstore(feynman_docs, scores=[0.5, 0.6]))
    monkeypatch.setattr("graph.papers_vectorstore", _FakeVectorstore(paper_docs, scores=[0.0, 0.1, 0.2, 0.3]))

    state = make_state(effort="medium")  # top_k=3
    result = retrieve(state)

    assert len(result["context"]) == 3
    mono_count = sum(1 for d in result["context"] if d.metadata.get("paper_id") == "arxiv:mono")
    assert mono_count == 2  # 캡(MAX_CHUNKS_PER_PAPER=2)에 걸려 3개·4개가 아니라 2개만
    assert any(d.metadata.get("source") == "feynman" for d in result["context"])  # 남은 자리는 feynman으로 채워짐
