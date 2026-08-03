"""
paper_screening.py — 논문 스크리닝(②b). invoke_with_fallback을 몽키패치해 순수 조립·
계산 로직만 검증 — 실제 LLM 호출 없음. screen_candidate()는 08-02에 관심사 dict 대신
자유 텍스트(topic)를 받도록 리팩터됐다 — ③ 추천 검색(관심사 4필드 조립)과 참고문헌
추천기(문장 하나) 양쪽이 같은 함수를 공유하기 위함(paper_recommend.py 참고).
"""
import pytest

import paper_screening


CANDIDATE = {
    "paper_id": "arxiv:2401.1",
    "abstract": "이 논문은 위상 물질의 새로운 상전이를 다룬다.",
    "journal_ref": "",
    "citation_count": None,
    "year": "2024",
}

TOPIC = (
    "제목: 위상 물질\n"
    "찾는 것: 새로운 상전이 발견\n"
    "이미 아는 것: 기본 개념\n"
    "제외할 주제: 초전도체"
)


def _fake_result(is_relevant, reasoning=""):
    return (
        paper_screening.RelevanceScreen(is_relevant=is_relevant, reasoning=reasoning),
        "gemini", [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def test_screen_candidate_returns_relevance_and_reasoning(monkeypatch):
    monkeypatch.setattr(
        paper_screening, "invoke_with_fallback",
        lambda *a, **kw: _fake_result(True, "관심사와 직접 관련"),
    )

    result = paper_screening.screen_candidate(CANDIDATE, TOPIC)

    assert result["paper_id"] == "arxiv:2401.1"
    assert result["is_relevant"] is True
    assert result["reasoning"] == "관심사와 직접 관련"


def test_screen_candidate_peer_reviewed_true_when_journal_ref_present(monkeypatch):
    monkeypatch.setattr(paper_screening, "invoke_with_fallback", lambda *a, **kw: _fake_result(True))

    candidate = {**CANDIDATE, "journal_ref": "Phys. Rev. D 100, 1 (2024)"}
    result = paper_screening.screen_candidate(candidate, TOPIC)

    assert result["peer_reviewed"] is True


def test_screen_candidate_peer_reviewed_false_when_journal_ref_empty(monkeypatch):
    monkeypatch.setattr(paper_screening, "invoke_with_fallback", lambda *a, **kw: _fake_result(True))

    result = paper_screening.screen_candidate(CANDIDATE, TOPIC)  # journal_ref == ""

    assert result["peer_reviewed"] is False


def test_screen_candidate_passes_through_citation_count_and_year_unchanged(monkeypatch):
    monkeypatch.setattr(paper_screening, "invoke_with_fallback", lambda *a, **kw: _fake_result(True))

    candidate = {**CANDIDATE, "citation_count": 42, "year": "2019"}
    result = paper_screening.screen_candidate(candidate, TOPIC)

    assert result["citation_count"] == 42  # 계산하지 않고 그대로 전달
    assert result["year"] == "2019"


def test_screen_candidate_citation_count_stays_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(paper_screening, "invoke_with_fallback", lambda *a, **kw: _fake_result(True))

    result = paper_screening.screen_candidate(CANDIDATE, TOPIC)  # citation_count: None

    assert result["citation_count"] is None  # 지어내지 않음(외부 API 어댑터 붙기 전)


def test_screen_candidate_prompt_includes_topic_and_abstract(monkeypatch):
    captured = {}
    def _fake_invoke(model, messages, structured=None):
        captured["human"] = messages[-1].content
        return _fake_result(True)
    monkeypatch.setattr(paper_screening, "invoke_with_fallback", _fake_invoke)

    paper_screening.screen_candidate(CANDIDATE, TOPIC)

    assert "새로운 상전이 발견" in captured["human"]  # 관심사 조립 텍스트의 looking_for
    assert "위상 물질의 새로운 상전이" in captured["human"]  # 후보의 abstract


def test_screen_candidate_accepts_plain_claim_as_topic(monkeypatch):
    # 관심사 4필드 조립 텍스트가 아니라 문장 하나만 와도 그대로 동작해야 한다 —
    # 참고문헌 추천기가 텍스트에서 뽑은 주장을 넘기는 경로(관심사 dict 불필요).
    captured = {}
    def _fake_invoke(model, messages, structured=None):
        captured["human"] = messages[-1].content
        return _fake_result(True)
    monkeypatch.setattr(paper_screening, "invoke_with_fallback", _fake_invoke)

    claim = "표면 부호는 국소적 안정자 측정만으로 오류를 검출할 수 있다"
    paper_screening.screen_candidate(CANDIDATE, claim)

    assert claim in captured["human"]


def test_screen_candidate_not_relevant(monkeypatch):
    monkeypatch.setattr(
        paper_screening, "invoke_with_fallback",
        lambda *a, **kw: _fake_result(False, "관심사와 무관"),
    )

    result = paper_screening.screen_candidate(CANDIDATE, TOPIC)
    assert result["is_relevant"] is False


def test_screen_candidate_propagates_model_failure(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(paper_screening, "invoke_with_fallback", _boom)

    with pytest.raises(RuntimeError):
        paper_screening.screen_candidate(CANDIDATE, TOPIC)
