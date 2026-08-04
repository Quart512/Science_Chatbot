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
        "peer_reviewed": False, "citation_count": None, "year": "2024",
        "tokens_used": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        "disabled_models": [],  # 서킷 브레이커를 후보 간에 이어주는 키(08-03 추가)
    }


# --- extract_search_query() --------------------------------------------------


def test_extract_search_query_returns_llm_query(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("표면 부호 오류정정"))

    query, _, _ = reference_recommender.extract_search_query("표면 부호는 국소적 안정자 측정만으로 오류를 검출한다")

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

    results, reason, _, _ = reference_recommender.recommend_references("텍스트", min_owned_results=3)

    assert [r["paper_id"] for r in results] == ["p1", "p2", "p3"]
    assert all(r["source"] == "owned" for r in results)
    assert reason is None


def test_recommend_references_owned_and_external_share_the_same_keys(monkeypatch):
    # source에 따라 키 집합이 달라지면 소비자(⑦ 논문 작성)가 r["reasoning"]에서 KeyError를
    # 맞는다 — 보유/신규 둘 다 같은 키를 갖는 것이 이 함수의 계약이다.
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", _FakeVectorstore([_owned_doc("p1", "논문1")]))
    monkeypatch.setattr(paper_search, "search_papers", lambda *a, **kw: [_candidate("arxiv:new", "새 논문")])
    monkeypatch.setattr(paper_screening, "screen_candidate", lambda candidate, topic, **kw: _screened("arxiv:new", True, "관련 있음"))

    results, _, _, _ = reference_recommender.recommend_references("텍스트", min_owned_results=3)

    assert len(results) == 2
    assert {frozenset(r) for r in results} == {frozenset({"paper_id", "title", "source", "reasoning"})}
    assert results[0]["reasoning"] == ""  # 보유 논문은 스크리닝을 안 거쳐 근거가 비어 있음


def test_recommend_references_searches_owned_chunks_deeper_than_max_results(monkeypatch):
    # 논문 한 편이 100청크를 넘으므로 k=max_results면 dedupe 후 1~2편만 남는다 —
    # 청크 깊이(k)와 논문 개수 상한(max_results)은 별개 축이어야 한다.
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    captured = {}

    class _CapturingVectorstore(_FakeVectorstore):
        def similarity_search_with_score(self, query, k=None):
            captured["k"] = k
            return super().similarity_search_with_score(query, k)

    monkeypatch.setattr(reference_recommender, "papers_vectorstore", _CapturingVectorstore([]))
    monkeypatch.setattr(paper_search, "search_papers", lambda *a, **kw: [])

    reference_recommender.recommend_references("텍스트", max_results=5)

    assert captured["k"] == 5 * reference_recommender.OWNED_CHUNK_DEPTH_FACTOR


def test_recommend_references_caps_owned_results_at_max_results(monkeypatch):
    # 깊이를 키운 대신 상한은 코드가 명시적으로 걸어야 한다 — 예전엔 k가 우연히 상한
    # 역할을 겸했다.
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    many = [_owned_doc(f"p{i}", f"논문{i}") for i in range(10)]
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", _FakeVectorstore(many))
    monkeypatch.setattr(paper_search, "search_papers", lambda *a, **kw: [])

    results, _, _, _ = reference_recommender.recommend_references("텍스트", max_results=3, min_owned_results=3)

    assert [r["paper_id"] for r in results] == ["p0", "p1", "p2"]  # 유사도 상위 3편만


def test_recommend_references_carries_circuit_breaker_across_candidates(monkeypatch):
    # 한 번의 호출 안에서도 앞 후보에서 죽은 모델을 뒤 후보가 다시 때리면 안 된다 —
    # 검색어 추출 → 후보1 → 후보2로 disabled_models가 이어져야 하고, 최종값은 밖으로 나간다.
    monkeypatch.setattr(
        reference_recommender, "invoke_with_fallback",
        lambda *a, **kw: (reference_recommender.SearchQuery(query="검색어"), "claude", ["gemini"],
                          {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}),
    )
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", _FakeVectorstore([]))
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda *a, **kw: [_candidate("arxiv:1"), _candidate("arxiv:2")],
    )

    seen = []
    def _fake_screen(candidate, topic, **kw):
        seen.append(list(kw["disabled_models"]))
        # 후보1을 돌면서 claude까지 죽었다고 가정 — 후보2는 그걸 알고 시작해야 한다
        result = _screened(candidate["paper_id"], True)
        result["disabled_models"] = ["gemini", "claude"]
        return result
    monkeypatch.setattr(paper_screening, "screen_candidate", _fake_screen)

    results, _reason, disabled_models, tokens_used = reference_recommender.recommend_references(
        "텍스트", min_owned_results=1
    )

    assert seen[0] == ["gemini"]              # 검색어 추출에서 죽은 모델을 이어받음
    assert seen[1] == ["gemini", "claude"]    # 후보1에서 죽은 모델까지 이어받음
    assert disabled_models == ["gemini", "claude"]
    assert len(results) == 2
    # 검색어 추출 1회 + 스크리닝 2회 = 3회분 토큰이 누적돼야 한다
    assert tokens_used == {"input_tokens": 3, "output_tokens": 3, "total_tokens": 6}


def test_recommend_references_dedupes_owned_by_paper_id(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    # 같은 논문의 청크 두 개가 검색될 수 있음(같은 paper_id) — 하나로 합쳐져야 함
    fake_vs = _FakeVectorstore([_owned_doc("p1", "논문1"), _owned_doc("p1", "논문1")])
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", fake_vs)
    monkeypatch.setattr(paper_search, "search_papers", lambda *a, **kw: [])

    results, _, _, _ = reference_recommender.recommend_references("텍스트", min_owned_results=1)

    assert [r["paper_id"] for r in results] == ["p1"]


def test_recommend_references_falls_back_to_external_search_when_owned_insufficient(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    fake_vs = _FakeVectorstore([_owned_doc("p1", "논문1")])  # 1개뿐 — min_owned_results=3 미달
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", fake_vs)
    monkeypatch.setattr(paper_search, "search_papers", lambda *a, **kw: [_candidate("arxiv:new", "새 논문")])
    monkeypatch.setattr(paper_screening, "screen_candidate", lambda candidate, topic, **kw: _screened("arxiv:new", True, "관련 있음"))

    results, _, _, _ = reference_recommender.recommend_references("텍스트", min_owned_results=3)

    assert [r["paper_id"] for r in results] == ["p1", "arxiv:new"]
    assert results[0]["source"] == "owned"
    assert results[1]["source"] == "external"
    assert results[1]["reasoning"] == "관련 있음"


def test_recommend_references_excludes_irrelevant_external_candidates(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", _FakeVectorstore([]))
    monkeypatch.setattr(paper_search, "search_papers", lambda *a, **kw: [_candidate("arxiv:no", "무관한 논문")])
    monkeypatch.setattr(paper_screening, "screen_candidate", lambda candidate, topic, **kw: _screened("arxiv:no", False))

    results, reason, _, _ = reference_recommender.recommend_references("텍스트", min_owned_results=1)

    assert results == []
    assert reason == "all_irrelevant"


def test_recommend_references_reason_is_no_candidates_when_search_returns_empty(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", _FakeVectorstore([]))
    monkeypatch.setattr(paper_search, "search_papers", lambda *a, **kw: [])

    results, reason, _, _ = reference_recommender.recommend_references("텍스트", min_owned_results=1)

    assert results == []
    assert reason == "no_candidates"


def test_recommend_references_reason_is_models_exhausted_when_screening_fails(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", _FakeVectorstore([]))
    monkeypatch.setattr(paper_search, "search_papers", lambda *a, **kw: [_candidate("arxiv:fail", "실패")])

    def _boom_screen(*a, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(paper_screening, "screen_candidate", _boom_screen)

    results, reason, _, _ = reference_recommender.recommend_references("텍스트", min_owned_results=1)

    assert results == []
    assert reason == "models_exhausted"


def test_recommend_references_raises_reference_search_error_on_network_failure(monkeypatch):
    import pytest
    import requests

    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", _FakeVectorstore([]))

    def _boom_search(*a, **kw):
        raise requests.exceptions.ConnectionError("arxiv 응답 없음 흉내")
    monkeypatch.setattr(paper_search, "search_papers", _boom_search)

    with pytest.raises(reference_recommender.ReferenceSearchError):
        reference_recommender.recommend_references("텍스트", min_owned_results=1)


def test_recommend_references_skips_external_candidate_on_screening_failure(monkeypatch):
    monkeypatch.setattr(reference_recommender, "invoke_with_fallback", lambda *a, **kw: _fake_query_result("검색어"))
    monkeypatch.setattr(reference_recommender, "papers_vectorstore", _FakeVectorstore([]))
    monkeypatch.setattr(
        paper_search, "search_papers",
        lambda *a, **kw: [_candidate("arxiv:fail", "실패"), _candidate("arxiv:ok", "성공")],
    )
    def _fake_screen(candidate, topic, **kw):
        if candidate["paper_id"] == "arxiv:fail":
            raise RuntimeError("전 모델 소진 흉내")
        return _screened("arxiv:ok", True)
    monkeypatch.setattr(paper_screening, "screen_candidate", _fake_screen)

    results, _, _, _ = reference_recommender.recommend_references("텍스트", min_owned_results=1)

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

    results, _, _, _ = reference_recommender.recommend_references("텍스트", min_owned_results=3)

    assert [r["paper_id"] for r in results] == ["p1"]
