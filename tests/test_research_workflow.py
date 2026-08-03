"""
research_workflow.py — 연구 워크플로우(⑥) 노드들. 그래프 노드를 맨 함수로 직접 부르는
이 저장소 관례(orchestrator.py 테스트와 동일) 그대로 invoke_with_fallback/
reference_recommender/equipment를 몽키패치해 순수 조립 로직만 검증 — 실제 LLM·벡터DB
호출 없음.
"""
import pytest

import equipment
import reference_recommender
import research_workflow


def _fake_result(disabled_models=None, statement="가설", rationale="근거", prediction="예측"):
    return (
        research_workflow.HypothesisOutput(statement=statement, rationale=rationale, testable_prediction=prediction),
        "gemini", disabled_models or [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def test_generate_hypothesis_returns_structured_fields(monkeypatch):
    monkeypatch.setattr(
        research_workflow, "invoke_with_fallback",
        lambda *a, **kw: _fake_result(statement="온도가 오르면 저항이 커진다", rationale="금속의 일반적 특성", prediction="온도-저항 그래프가 우상향"),
    )

    state = research_workflow.WorkflowState(topic="금속의 전기저항은 온도에 어떻게 의존하는가")
    result = research_workflow.generate_hypothesis(state)

    assert result["hypothesis"] == "온도가 오르면 저항이 커진다"
    assert result["rationale"] == "금속의 일반적 특성"
    assert result["testable_prediction"] == "온도-저항 그래프가 우상향"


def test_generate_hypothesis_passes_disabled_models_through(monkeypatch):
    # physics_qa_node/draft_interest_from_messages와 같은 서킷 브레이커 패턴 —
    # 넘긴 disabled_models가 invoke_with_fallback에 그대로 전달되고, 갱신된 값이
    # 반환값에 실려야 한다.
    captured = {}
    def _fake_invoke(model, messages, structured=None, disabled_models=None):
        captured["disabled_models"] = disabled_models
        return _fake_result(disabled_models=disabled_models + ["gemini"])
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _fake_invoke)

    state = research_workflow.WorkflowState(topic="주제", disabled_models=["claude"])
    result = research_workflow.generate_hypothesis(state)

    assert captured["disabled_models"] == ["claude"]
    assert result["disabled_models"] == ["claude", "gemini"]


def test_generate_hypothesis_accumulates_tokens(monkeypatch):
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", lambda *a, **kw: _fake_result())

    state = research_workflow.WorkflowState(
        topic="주제", tokens_used={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    )
    result = research_workflow.generate_hypothesis(state)

    assert result["tokens_used"] == {"input_tokens": 11, "output_tokens": 6, "total_tokens": 17}


def test_generate_hypothesis_propagates_model_failure(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _boom)

    state = research_workflow.WorkflowState(topic="주제")
    with pytest.raises(RuntimeError):
        research_workflow.generate_hypothesis(state)


# --- find_hypothesis_references() -------------------------------------------


def _ref(paper_id, title="", source="owned", reasoning=""):
    return {"paper_id": paper_id, "title": title, "source": source, "reasoning": reasoning}


def test_find_hypothesis_references_appends_with_stage_tag(monkeypatch):
    monkeypatch.setattr(
        reference_recommender, "recommend_references",
        lambda text: [_ref("p1", "논문1"), _ref("p2", "논문2", source="external", reasoning="관련 있음")],
    )

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설 문장")
    result = research_workflow.find_hypothesis_references(state)

    assert [r["paper_id"] for r in result["references"]] == ["p1", "p2"]
    assert all(r["added_by_stage"] == "hypothesis" for r in result["references"])


def test_find_hypothesis_references_searches_using_hypothesis_text(monkeypatch):
    captured = {}
    def _fake_recommend(text):
        captured["text"] = text
        return []
    monkeypatch.setattr(reference_recommender, "recommend_references", _fake_recommend)

    state = research_workflow.WorkflowState(topic="주제", hypothesis="온도가 오르면 저항이 커진다")
    research_workflow.find_hypothesis_references(state)

    assert captured["text"] == "온도가 오르면 저항이 커진다"


def test_find_hypothesis_references_dedupes_against_existing(monkeypatch):
    monkeypatch.setattr(
        reference_recommender, "recommend_references",
        lambda text: [_ref("p1", "이미 있음"), _ref("p2", "새 논문")],
    )

    state = research_workflow.WorkflowState(
        topic="주제", hypothesis="가설",
        references=[{**_ref("p1", "이미 있음"), "added_by_stage": "design"}],
    )
    result = research_workflow.find_hypothesis_references(state)

    assert [r["paper_id"] for r in result["references"]] == ["p1", "p2"]
    assert result["references"][0]["added_by_stage"] == "design"  # 원래 태그 유지(안 덮어씀)


def test_find_hypothesis_references_skips_step_on_failure(monkeypatch):
    def _boom(text):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(reference_recommender, "recommend_references", _boom)

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    result = research_workflow.find_hypothesis_references(state)

    assert "references" not in result  # 워크플로우를 안 막음 — references 안 건드림
    assert "검토" in result["comment"]  # 실패했다는 사실은 사용자에게 안내


def test_find_hypothesis_references_comment_guides_review_when_found(monkeypatch):
    monkeypatch.setattr(reference_recommender, "recommend_references", lambda text: [_ref("p1", "논문1")])

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    result = research_workflow.find_hypothesis_references(state)

    assert "선행 연구" in result["comment"]
    assert "재생성" in result["comment"]


def test_find_hypothesis_references_comment_suggests_regenerate_when_none_found(monkeypatch):
    monkeypatch.setattr(reference_recommender, "recommend_references", lambda text: [])

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    result = research_workflow.find_hypothesis_references(state)

    assert result["references"] == []
    assert "재생성" in result["comment"]


def test_find_hypothesis_references_comment_suggests_regenerate_when_all_duplicates(monkeypatch):
    # recommend_references가 뭔가 찾았어도 전부 이미 있는 paper_id면 "새로 찾은 것"은
    # 없으므로 "못 찾음" 안내와 같은 취급이어야 한다.
    monkeypatch.setattr(reference_recommender, "recommend_references", lambda text: [_ref("p1", "이미 있음")])

    state = research_workflow.WorkflowState(
        topic="주제", hypothesis="가설",
        references=[{**_ref("p1", "이미 있음"), "added_by_stage": "design"}],
    )
    result = research_workflow.find_hypothesis_references(state)

    assert "재생성" in result["comment"]
    assert "선행 연구" not in result["comment"]


# --- design_experiment() ------------------------------------------------------


def _fake_design_result(disabled_models=None, **fields):
    defaults = dict(
        independent_variable="온도", dependent_variable="저항",
        controlled_variables="시료 순도", equipment_needed="온도 조절 장치",
        procedure="1. 시료를 냉각한다\n2. 저항을 측정한다",
    )
    return (
        research_workflow.ExperimentDesign(**{**defaults, **fields}),
        "gemini", disabled_models or [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def test_design_experiment_returns_structured_fields(monkeypatch):
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", lambda *a, **kw: _fake_design_result())
    monkeypatch.setattr(equipment, "list_equipment", lambda **kw: [])

    state = research_workflow.WorkflowState(topic="주제", hypothesis="온도가 오르면 저항이 커진다")
    result = research_workflow.design_experiment(state)

    assert result["independent_variable"] == "온도"
    assert result["dependent_variable"] == "저항"
    assert result["controlled_variables"] == "시료 순도"
    assert result["equipment_needed"] == "온도 조절 장치"
    assert "저항을 측정한다" in result["procedure"]


def test_design_experiment_includes_equipment_list_in_prompt(monkeypatch):
    monkeypatch.setattr(
        equipment, "list_equipment",
        lambda **kw: [{"id": 1, "name": "오실로스코프", "purpose": "파형 관찰", "detail": ""}],
    )
    captured = {}
    def _fake_invoke(model, messages, structured=None, disabled_models=None):
        captured["human"] = messages[-1].content
        return _fake_design_result()
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _fake_invoke)

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    research_workflow.design_experiment(state)

    assert "오실로스코프" in captured["human"]
    assert "파형 관찰" in captured["human"]


def test_design_experiment_notes_when_no_equipment_registered(monkeypatch):
    monkeypatch.setattr(equipment, "list_equipment", lambda **kw: [])
    captured = {}
    def _fake_invoke(model, messages, structured=None, disabled_models=None):
        captured["human"] = messages[-1].content
        return _fake_design_result()
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _fake_invoke)

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    research_workflow.design_experiment(state)

    assert "등록된 장비 없음" in captured["human"]


def test_design_experiment_passes_disabled_models_through(monkeypatch):
    monkeypatch.setattr(equipment, "list_equipment", lambda **kw: [])
    captured = {}
    def _fake_invoke(model, messages, structured=None, disabled_models=None):
        captured["disabled_models"] = disabled_models
        return _fake_design_result(disabled_models=disabled_models + ["gemini"])
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _fake_invoke)

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설", disabled_models=["claude"])
    result = research_workflow.design_experiment(state)

    assert captured["disabled_models"] == ["claude"]
    assert result["disabled_models"] == ["claude", "gemini"]


def test_design_experiment_propagates_model_failure(monkeypatch):
    monkeypatch.setattr(equipment, "list_equipment", lambda **kw: [])
    def _boom(*a, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _boom)

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    with pytest.raises(RuntimeError):
        research_workflow.design_experiment(state)


# --- find_design_references() --------------------------------------------------


def test_find_design_references_searches_using_procedure_text(monkeypatch):
    captured = {}
    def _fake_recommend(text):
        captured["text"] = text
        return []
    monkeypatch.setattr(reference_recommender, "recommend_references", _fake_recommend)

    state = research_workflow.WorkflowState(topic="주제", procedure="1. 시료를 냉각한다\n2. 저항을 측정한다")
    research_workflow.find_design_references(state)

    assert captured["text"] == "1. 시료를 냉각한다\n2. 저항을 측정한다"


def test_find_design_references_appends_with_stage_tag(monkeypatch):
    monkeypatch.setattr(reference_recommender, "recommend_references", lambda text: [_ref("p1", "논문1")])

    state = research_workflow.WorkflowState(topic="주제", procedure="절차")
    result = research_workflow.find_design_references(state)

    assert result["references"][0]["added_by_stage"] == "design"


# --- advance_to_design() ------------------------------------------------------
# 그래프 자동 엣지가 아니라 사용자가 "설계 진행"을 트리거했을 때 main.py가
# aget_state/aupdate_state로 감싸 부를 평범한 함수(08-02, 사용자 판단). 여기선 그래프
# 없이 함수만 직접 검증 — aget_state/aupdate_state 배관은 main.py에 실제로 붙일 때 확인.


def test_advance_to_design_combines_design_and_reference_updates(monkeypatch):
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", lambda *a, **kw: _fake_design_result())
    monkeypatch.setattr(equipment, "list_equipment", lambda **kw: [])
    monkeypatch.setattr(reference_recommender, "recommend_references", lambda text: [_ref("p1", "논문1")])

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    result = research_workflow.advance_to_design(state)

    assert result["procedure"] == "1. 시료를 냉각한다\n2. 저항을 측정한다"
    assert result["references"][0]["paper_id"] == "p1"
    assert result["references"][0]["added_by_stage"] == "design"
    assert "재생성" in result["comment"]


def test_advance_to_design_searches_references_using_freshly_designed_procedure(monkeypatch):
    # find_design_references가 advance_to_design 호출 시점의 낡은 state.procedure(빈 값)가
    # 아니라 방금 design_experiment가 만든 procedure로 검색해야 한다 — 그래서 두 호출을
    # 하나로 합칠 때 중간 state를 갱신해서 넘기는지가 이 테스트의 핵심.
    monkeypatch.setattr(
        research_workflow, "invoke_with_fallback",
        lambda *a, **kw: _fake_design_result(procedure="새로 설계된 절차"),
    )
    monkeypatch.setattr(equipment, "list_equipment", lambda **kw: [])
    captured = {}
    def _fake_recommend(text):
        captured["text"] = text
        return []
    monkeypatch.setattr(reference_recommender, "recommend_references", _fake_recommend)

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설", procedure="")
    research_workflow.advance_to_design(state)

    assert captured["text"] == "새로 설계된 절차"


def test_advance_to_design_does_not_mutate_original_state(monkeypatch):
    # model_copy(update=...)는 새 객체를 만들어야 한다 — 원래 state 객체를 직접
    # 건드리면 호출자(aget_state로 읽은 스냅샷)가 예상 못 한 부작용을 겪는다.
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", lambda *a, **kw: _fake_design_result())
    monkeypatch.setattr(equipment, "list_equipment", lambda **kw: [])
    monkeypatch.setattr(reference_recommender, "recommend_references", lambda text: [])

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    research_workflow.advance_to_design(state)

    assert state.procedure == ""  # 원본은 그대로
