"""
reference_recommender.py — 참고문헌 추천기(⑥ 착수, 2단계). invoke_with_fallback/
paper_search.search_papers/paper_screening.screen_candidate를 몽키패치해 순수 조립·
분기 로직만 검증 — 실제 LLM·벡터DB·네트워크 없음. papers_vectorstore는 conftest.py가
retrieval 모듈 자체를 스텁해두므로(무거운 임베딩 로딩 방지) tests/test_retrieve.py와
같은 패턴(_FakeVectorstore)으로 이 모듈의 이름을 직접 갈아끼운다.
"""
from langchain_core.documents import Document

import paper_screening
import paper_search
import reference_recommender


class _FakeVectorstore:
    def __init__(self, docs, scores=None):
        self.docs = docs
        self.scores = scores if scores is not None else [float(i) for i in range(len(docs))]

    def similarity_search_with_score(self, query, k=None):
        scored = list(zip(self.docs, self.scores))
        return scored[:k] if k is not None else scored


def _owned_doc(paper_id: str, title: str = "") -> Document:
    return Document(page_content="본문", metadata={"paper_id": paper_id, "title": title, "doc_type": "fulltext_chunk"})


def _candidate(paper_id: str, title: str = "") -> dict:
    return {
        "paper_id": paper_id, "doi": None, "arxiv_id": paper_id, "title": title,
        "authors": [], "year": "2024", "abstract": "초록", "pdf_url": "", "journal_ref": "", "citation_count": None,
    }


def _fake_query_result(query: str):
    return (
        reference_recommender.SearchQuery(query=query),
        "gemini", [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def _screened(paper_id: str, is_relevant: bool, reasoning: str = ""):
    return {
        "paper_id": paper_id, "is_relevant": is_relevant, "reasoning": reasoning,
        "peer_reviewed": False, "citation_count": None, "year": "2024", "tokens_used": {},
    }


# --- extract_search_query() --------------------------------------------------


def test_extract_search_query_returns_llm_query(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("표면 부호 오류정정"))

    query = reference_recommender.extract_search_query("표면 부호는 국소적 안정자 측정만으로 오류를 검출한다")

    assert query == "표면 부호 오류정정"


def test_extract_search_query_propagates_model_failure(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", _boom)

    import pytest
    with pytest.raises(RuntimeError):
        reference_recommender.extract_search_query("텍스트")


# --- recommend_references() ---------------------------------------------------


def test_recommend_references_returns_owned_only_when_enough(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    fake_vs = _FakeVectorstore([_owned_doc("p1", "논문1"), _owned_doc("p2", "논문2"), _owned_doc("p3", "논문3")])
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", fake_vs)

    def _boom_search(*a, **kw):
        raise AssertionError("보유 논문이 충분하면 신규 검색을 하면 안 됨")
    monkeypatch.setattr(paper_search, "search_papers", _boom_search)

    results = reference_recommender.recommend_references("텍스트", min_owned_results=3)

    assert [r["paper_id"] for r in results] == ["p1", "p2", "p3"]
    assert all(r["source"] == "owned" for r in results)


def test_recommend_references_dedupes_owned_by_paper_id(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    # 같은 논문의 청크 두 개가 검색될 수 있음(같은 paper_id) — 하나로 합쳐져야 함
    fake_vs = _FakeVectorstore([_owned_doc("p1", "논문1"), _owned_doc("p1", "논문1")])
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", fake_vs)
    monkeypatch.setattr(paper_search, "search_papers", lambda *a, **kw: [])

    results = reference_recommender.recommend_references("텍스트", min_owned_results=1)

    assert [r["paper_id"] for r in results] == ["p1"]


def test_recommend_references_falls_back_to_external_search_when_owned_insufficient(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    fake_vs = _FakeVectorstore([_owned_doc("p1", "논문1")])  # 1개뿐 — min_owned_results=3 미달
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", fake_vs)
    monkeypatch.setattr(paper_search, "search_papers", lambda *a, **kw: [_candidate("arxiv:new", "새 논문")])
    monkeypatch.setattr(paper_screening, "screen_candidate", lambda candidate, topic: _screened("arxiv:new", True, "관련 있음"))

    results = reference_recommender.recommend_references("텍스트", min_owned_results=3)

    assert [r["paper_id"] for r in results] == ["p1", "arxiv:new"]
    assert results[0]["source"] == "owned"
    assert results[1]["source"] == "external"
    assert results[1]["reasoning"] == "관련 있음"


def test_recommend_references_excludes_irrelevant_external_candidates(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", _FakeVectorstore([]))
    monkeypatch.setattr(paper_search, "search_papers", lambda *a, **kw: [_candidate("arxiv:no", "무관한 논문")])
    monkeypatch.setattr(paper_screening, "screen_candidate", lambda candidate, topic: _screened("arxiv:no", False))

    results = reference_recommender.recommend_references("텍스트", min_owned_results=1)

    assert results == []


def test_recommend_references_skips_external_candidate_on_screening_failure(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", _FakeVectorstore([]))
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda *a, **kw: [_candidate("arxiv:fail", "실패"), _candidate("arxiv:ok", "성공")],
    )
    def _fake_screen(candidate, topic):
        if candidate["paper_id"] == "arxiv:fail":
            raise RuntimeError("전 모델 소진 흉내")
        return _screened("arxiv:ok", True)
    monkeypatch.setattr(paper_screening, "screen_candidate", _fake_screen)

    results = reference_recommender.recommend_references("텍스트", min_owned_results=1)

    assert [r["paper_id"] for r in results] == ["arxiv:ok"]


def test_recommend_references_external_search_excludes_already_owned_paper_ids(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    fake_vs = _FakeVectorstore([_owned_doc("p1", "논문1")])
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", fake_vs)
    # 신규 검색이 이미 보유 중인 p1을 다시 돌려주는 경우 — 중복으로 추가되면 안 됨
    monkeypatch.setattr(paper_search, "search_papers", lambda *a, **kw: [_candidate("p1", "논문1")])
    def _boom_screen(*a, **kw):
        raise AssertionError("이미 보유한 논문은 스크리닝도 할 필요 없이 건너뛰어야 함")
    monkeypatch.setattr(paper_screening, "screen_candidate", _boom_screen)

    results = reference_recommender.recommend_references("텍스트", min_owned_results=3)

    assert [r["paper_id"] for r in results] == ["p1"]
