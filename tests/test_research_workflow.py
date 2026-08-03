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


_TOKENS = {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}


def _returning(refs, disabled_models=None):
    """recommend_references 대역 — 계약이 (목록, disabled_models, tokens_used) 3튜플이라
    테스트마다 튜플을 손으로 쓰지 않게 감싼다. **kw를 받는 이유는 노드가 항상
    disabled_models=를 키워드로 넘기기 때문."""
    return lambda text, **kw: (refs, disabled_models or [], _TOKENS)


def test_find_hypothesis_references_appends_with_stage_tag(monkeypatch):
    monkeypatch.setattr(
        reference_recommender, "recommend_references",
        _returning([_ref("p1", "논문1"), _ref("p2", "논문2", source="external", reasoning="관련 있음")]),
    )

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설 문장")
    result = research_workflow.find_hypothesis_references(state)

    assert [r["paper_id"] for r in result["references"]] == ["p1", "p2"]
    assert all(r["added_by_stage"] == "hypothesis" for r in result["references"])


def test_find_hypothesis_references_searches_using_hypothesis_text(monkeypatch):
    captured = {}
    def _fake_recommend(text, **kw):
        captured["text"] = text
        return [], [], _TOKENS
    monkeypatch.setattr(reference_recommender, "recommend_references", _fake_recommend)

    state = research_workflow.WorkflowState(topic="주제", hypothesis="온도가 오르면 저항이 커진다")
    research_workflow.find_hypothesis_references(state)

    assert captured["text"] == "온도가 오르면 저항이 커진다"


def test_find_hypothesis_references_dedupes_against_existing(monkeypatch):
    monkeypatch.setattr(
        reference_recommender, "recommend_references",
        _returning([_ref("p1", "이미 있음"), _ref("p2", "새 논문")]),
    )

    state = research_workflow.WorkflowState(
        topic="주제", hypothesis="가설",
        references=[{**_ref("p1", "이미 있음"), "added_by_stage": "design"}],
    )
    result = research_workflow.find_hypothesis_references(state)

    assert [r["paper_id"] for r in result["references"]] == ["p1", "p2"]
    assert result["references"][0]["added_by_stage"] == "design"  # 원래 태그 유지(안 덮어씀)


def test_find_hypothesis_references_shares_circuit_breaker_and_tokens(monkeypatch):
    # 이 노드가 워크플로우에서 LLM을 가장 많이 부르는 지점(검색어 추출 1 + 스크리닝 N)이라
    # 다른 노드와 똑같이 disabled_models를 넘겨받고 갱신값·토큰을 State에 돌려줘야 한다 —
    # 안 하면 앞 단계에서 죽은 모델을 후보마다 다시 때려본다.
    captured = {}
    def _fake_recommend(text, **kw):
        captured["disabled_models"] = kw.get("disabled_models")
        return [], ["claude", "gemini"], _TOKENS
    monkeypatch.setattr(reference_recommender, "recommend_references", _fake_recommend)

    state = research_workflow.WorkflowState(
        topic="주제", hypothesis="가설", disabled_models=["claude"],
        tokens_used={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    )
    result = research_workflow.find_hypothesis_references(state)

    assert captured["disabled_models"] == ["claude"]
    assert result["disabled_models"] == ["claude", "gemini"]
    assert result["tokens_used"] == {"input_tokens": 11, "output_tokens": 6, "total_tokens": 17}


def test_find_hypothesis_references_skips_step_on_failure(monkeypatch):
    def _boom(text, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(reference_recommender, "recommend_references", _boom)

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    result = research_workflow.find_hypothesis_references(state)

    assert "references" not in result  # 워크플로우를 안 막음 — references 안 건드림
    assert "검토" in result["comment"]  # 실패했다는 사실은 사용자에게 안내


def test_find_hypothesis_references_skips_step_on_network_failure(monkeypatch):
    # 모델 소진(RuntimeError)뿐 아니라 arxiv 네트워크 장애도 이 단계만 건너뛰어야 한다 —
    # 여기서 예외가 새면 방금 만든 가설이 체크포인트에 커밋되지 못하고 날아간다.
    import requests

    def _boom(text, **kw):
        raise requests.exceptions.ConnectionError("arxiv 응답 없음 흉내")
    monkeypatch.setattr(reference_recommender, "recommend_references", _boom)

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    result = research_workflow.find_hypothesis_references(state)

    assert "references" not in result
    assert "검토" in result["comment"]


def test_find_hypothesis_references_comment_guides_review_when_found(monkeypatch):
    monkeypatch.setattr(reference_recommender, "recommend_references", _returning([_ref("p1", "논문1")]))

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    result = research_workflow.find_hypothesis_references(state)

    assert "선행 연구" in result["comment"]
    assert "재생성" in result["comment"]


def test_find_hypothesis_references_comment_suggests_regenerate_when_none_found(monkeypatch):
    monkeypatch.setattr(reference_recommender, "recommend_references", _returning([]))

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    result = research_workflow.find_hypothesis_references(state)

    assert result["references"] == []
    assert "재생성" in result["comment"]


def test_find_hypothesis_references_comment_suggests_regenerate_when_all_duplicates(monkeypatch):
    # recommend_references가 뭔가 찾았어도 전부 이미 있는 paper_id면 "새로 찾은 것"은
    # 없으므로 "못 찾음" 안내와 같은 취급이어야 한다.
    monkeypatch.setattr(reference_recommender, "recommend_references", _returning([_ref("p1", "이미 있음")]))

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


def test_design_experiment_includes_testable_prediction_in_prompt(monkeypatch):
    # analyze_results가 이 예측으로 성패를 판정하므로, 설계 단계가 예측을 보고
    # "측정 가능하게" 짜야 한다.
    monkeypatch.setattr(equipment, "list_equipment", lambda **kw: [])
    captured = {}
    def _fake_invoke(model, messages, structured=None, disabled_models=None):
        captured["human"] = messages[-1].content
        return _fake_design_result()
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _fake_invoke)

    state = research_workflow.WorkflowState(
        topic="주제", hypothesis="가설", testable_prediction="온도-저항 그래프가 우상향",
    )
    research_workflow.design_experiment(state)

    assert "온도-저항 그래프가 우상향" in captured["human"]


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
    def _fake_recommend(text, **kw):
        captured["text"] = text
        return [], [], _TOKENS
    monkeypatch.setattr(reference_recommender, "recommend_references", _fake_recommend)

    state = research_workflow.WorkflowState(topic="주제", procedure="1. 시료를 냉각한다\n2. 저항을 측정한다")
    research_workflow.find_design_references(state)

    assert captured["text"] == "1. 시료를 냉각한다\n2. 저항을 측정한다"


def test_find_design_references_appends_with_stage_tag(monkeypatch):
    monkeypatch.setattr(reference_recommender, "recommend_references", _returning([_ref("p1", "논문1")]))

    state = research_workflow.WorkflowState(topic="주제", procedure="절차")
    result = research_workflow.find_design_references(state)

    assert result["references"][0]["added_by_stage"] == "design"


# --- analyze_results() ---------------------------------------------------------


def _fake_analysis_result(disabled_models=None, analysis="예측을 지지함", outcome="supported"):
    return (
        research_workflow.ExperimentAnalysis(analysis=analysis, outcome=outcome),
        "gemini", disabled_models or [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def test_analyze_results_returns_structured_fields(monkeypatch):
    monkeypatch.setattr(
        research_workflow, "invoke_with_fallback",
        lambda *a, **kw: _fake_analysis_result(analysis="예측과 일치", outcome="supported"),
    )

    state = research_workflow.WorkflowState(
        topic="주제", hypothesis="가설", testable_prediction="예측", procedure="절차",
        experiment_results="측정값이 예측과 같았다",
    )
    result = research_workflow.analyze_results(state)

    assert result["analysis"] == "예측과 일치"
    assert result["outcome"] == "supported"


def test_analyze_results_sets_comment_from_outcome_guidance(monkeypatch):
    # comment는 LLM이 자유롭게 쓴 문장이 아니라 outcome별로 고정된 코드 문구여야 한다
    # (WorkflowState.comment의 "결정론적 안내" 원칙과 같은 결).
    monkeypatch.setattr(
        research_workflow, "invoke_with_fallback",
        lambda *a, **kw: _fake_analysis_result(outcome="design_flawed"),
    )

    state = research_workflow.WorkflowState(topic="주제")
    result = research_workflow.analyze_results(state)

    assert result["comment"] == research_workflow.OUTCOME_GUIDANCE["design_flawed"]
    assert "재설계" in result["comment"]


@pytest.mark.parametrize("outcome", [
    "supported", "hypothesis_wrong", "design_flawed", "execution_error", "analysis_error",
])
def test_analyze_results_every_outcome_has_guidance(monkeypatch, outcome):
    # ExperimentAnalysis.outcome의 Literal 값 다섯 개가 전부 OUTCOME_GUIDANCE에 있는지 —
    # 하나라도 빠지면 그 갈래가 나왔을 때 analyze_results가 KeyError로 죽는다.
    monkeypatch.setattr(
        research_workflow, "invoke_with_fallback",
        lambda *a, **kw: _fake_analysis_result(outcome=outcome),
    )

    state = research_workflow.WorkflowState(topic="주제")
    result = research_workflow.analyze_results(state)

    assert result["comment"] == research_workflow.OUTCOME_GUIDANCE[outcome]


def test_analyze_results_uses_experiment_results_in_prompt(monkeypatch):
    captured = {}
    def _fake_invoke(model, messages, structured=None, disabled_models=None):
        captured["human"] = messages[-1].content
        return _fake_analysis_result()
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _fake_invoke)

    state = research_workflow.WorkflowState(
        topic="주제", hypothesis="가설", testable_prediction="예측", procedure="절차",
        experiment_results="저항이 거의 안 변했다",
    )
    research_workflow.analyze_results(state)

    assert "저항이 거의 안 변했다" in captured["human"]


def test_analyze_results_passes_disabled_models_through(monkeypatch):
    captured = {}
    def _fake_invoke(model, messages, structured=None, disabled_models=None):
        captured["disabled_models"] = disabled_models
        return _fake_analysis_result(disabled_models=disabled_models + ["gemini"])
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _fake_invoke)

    state = research_workflow.WorkflowState(topic="주제", disabled_models=["claude"])
    result = research_workflow.analyze_results(state)

    assert captured["disabled_models"] == ["claude"]
    assert result["disabled_models"] == ["claude", "gemini"]


def test_analyze_results_propagates_model_failure(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("전 모델 소진 흉내")
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _boom)

    state = research_workflow.WorkflowState(topic="주제")
    with pytest.raises(RuntimeError):
        research_workflow.analyze_results(state)


# --- find_operation_references() ------------------------------------------------


def test_find_operation_references_searches_using_analysis_text(monkeypatch):
    captured = {}
    def _fake_recommend(text, **kw):
        captured["text"] = text
        return [], [], _TOKENS
    monkeypatch.setattr(reference_recommender, "recommend_references", _fake_recommend)

    state = research_workflow.WorkflowState(topic="주제", analysis="결과가 예측과 어긋났다")
    research_workflow.find_operation_references(state)

    assert captured["text"] == "결과가 예측과 어긋났다"


def test_find_operation_references_appends_with_stage_tag(monkeypatch):
    monkeypatch.setattr(reference_recommender, "recommend_references", _returning([_ref("p1", "논문1")]))

    state = research_workflow.WorkflowState(topic="주제", analysis="분석")
    result = research_workflow.find_operation_references(state)

    assert result["references"][0]["added_by_stage"] == "operation"


def test_find_operation_references_preserves_prior_comment(monkeypatch):
    # operation 체인은 analyze_results → find_operation_references 순으로 이어진다.
    # analyze_results가 남긴 갈래별 안내(comment)를 이 노드가 덮어쓰면 사람에게 그
    # 안내가 아예 전달되지 않는다 — 기존 comment 뒤에 이어붙여야 한다.
    monkeypatch.setattr(reference_recommender, "recommend_references", _returning([_ref("p1", "논문1")]))

    state = research_workflow.WorkflowState(
        topic="주제", analysis="분석", comment="실험 설계에 문제가 있어 보입니다 — 재설계를 눌러주세요.",
    )
    result = research_workflow.find_operation_references(state)

    assert result["comment"].startswith("실험 설계에 문제가 있어 보입니다")
    assert "선행 연구" in result["comment"]


def test_find_hypothesis_references_does_not_prepend_when_no_prior_comment(monkeypatch):
    # comment가 처음부터 비어 있으면(가설 단계는 analyze_results를 안 거침) 안내 문구
    # 앞에 빈 줄이 남지 않아야 한다.
    monkeypatch.setattr(reference_recommender, "recommend_references", _returning([_ref("p1", "논문1")]))

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    result = research_workflow.find_hypothesis_references(state)

    assert result["comment"].startswith("참고논문을 확인해서")


# --- compile_experiment_report() (⑦ 착수, 08-03) --------------------------------


def test_compile_experiment_report_includes_all_stage_fields():
    # LLM 호출 없는 순수 재포맷 — 가설·설계·운영 필드가 전부 보고서 텍스트에 그대로
    # 나타나야 한다(재종합이 아니므로 문구가 안 바뀜).
    state = research_workflow.WorkflowState(
        topic="주제",
        hypothesis="온도가 오르면 저항이 커진다", rationale="금속의 일반적 특성",
        testable_prediction="온도-저항 그래프가 우상향",
        independent_variable="온도", dependent_variable="저항", controlled_variables="시료 순도",
        equipment_needed="온도 조절 장치", procedure="1. 냉각한다\n2. 측정한다",
        experiment_results="저항이 거의 안 변했다", analysis="예측과 어긋남", outcome="execution_error",
    )
    result = research_workflow.compile_experiment_report(state)
    report = result["experiment_report"]

    for text in [
        "온도가 오르면 저항이 커진다", "금속의 일반적 특성", "온도-저항 그래프가 우상향",
        "온도", "저항", "시료 순도", "온도 조절 장치", "1. 냉각한다\n2. 측정한다",
        "저항이 거의 안 변했다", "예측과 어긋남", "실행 과정 오류로 추정",
    ]:
        assert text in report


def test_compile_experiment_report_labels_unset_outcome():
    # analyze_results를 아직 안 거친 상태(outcome="")로 report를 만들면 빈 라벨 대신
    # "미분석"임을 명시해야 한다 — 빈 문자열을 그냥 이어붙이면 무슨 값인지 안 보임.
    state = research_workflow.WorkflowState(topic="주제")
    result = research_workflow.compile_experiment_report(state)

    assert "(미분석)" in result["experiment_report"]


def test_compile_experiment_report_makes_no_llm_call(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("보고서 조립은 결정론적 재포맷이라 LLM을 부르면 안 됨")
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", _boom)

    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    research_workflow.compile_experiment_report(state)  # 예외 없이 끝나야 함


def test_compile_experiment_report_does_not_touch_tokens_or_disabled_models():
    # LLM을 안 부르므로 다른 노드와 달리 tokens_used/disabled_models를 반환에 안 실어야
    # 한다 — 실었다면 안 바뀐 값을 굳이 덮어쓰는 낭비 반환이다.
    state = research_workflow.WorkflowState(topic="주제", hypothesis="가설")
    result = research_workflow.compile_experiment_report(state)

    assert "tokens_used" not in result
    assert "disabled_models" not in result


# --- route_by_stage() + 그래프 라우팅 통합 확인 --------------------------------
# 단계 전환은 글루 함수(advance_to_design, 폐기됨)가 아니라 START의 조건부 엣지가
# state.stage를 보고 담당한다(08-02, 사용자 제안 — 토이 그래프로 실제 동작 확인 후
# 채택). 여기서는 route_by_stage() 자체(순수 함수)와, 실제 컴파일된 그래프가 stage
# 갱신 후 재호출 시 올바른 노드로 가는지(+ 이전 단계 값을 그대로 보는지)를 인메모리
# 체크포인터(MemorySaver, 파일 I/O 없음)로 확인한다.


def test_route_by_stage_returns_stage_field():
    state = research_workflow.WorkflowState(topic="주제", stage="design")
    assert research_workflow.route_by_stage(state) == "design"


def test_graph_routes_through_all_four_stages_via_single_invoke_calls(monkeypatch):
    # 단계 전환은 별도 update_state 호출 없이 stage(+새 입력)를 담은 ainvoke() 한 번으로
    # 된다는 것까지 포함해 확인 — 가설→설계→운영→보고서를 실제 컴파일된 그래프로 쭉 따라간다.
    from langgraph.checkpoint.memory import MemorySaver

    monkeypatch.setattr(research_workflow, "invoke_with_fallback", lambda *a, **kw: _fake_result(statement="가설X"))
    monkeypatch.setattr(reference_recommender, "recommend_references", _returning([]))

    app = research_workflow.graph.compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t1"}}

    first = app.invoke({"topic": "주제"}, config=config)
    assert first["hypothesis"] == "가설X"  # 기본 stage="hypothesis" → generate_hypothesis로 라우팅됨

    # design 단계 로직으로 갈아끼움(가설 생성 몽키패치가 그대로면 design_experiment의
    # invoke_with_fallback 호출도 HypothesisOutput을 기대하게 되므로 별도로 갈아끼움)
    monkeypatch.setattr(research_workflow, "invoke_with_fallback", lambda *a, **kw: _fake_design_result())
    monkeypatch.setattr(equipment, "list_equipment", lambda **kw: [])

    second = app.invoke({"stage": "design"}, config=config)  # update_state 없이 한 번의 호출로 전환

    assert second["procedure"] == "1. 시료를 냉각한다\n2. 저항을 측정한다"  # design_experiment로 라우팅됨
    assert second["hypothesis"] == "가설X"  # 1단계에서 저장된 값을 그대로 봄

    monkeypatch.setattr(
        research_workflow, "invoke_with_fallback",
        lambda *a, **kw: _fake_analysis_result(analysis="어긋남", outcome="design_flawed"),
    )

    third = app.invoke(
        {"stage": "operation", "experiment_results": "저항이 거의 안 변했다"}, config=config,
    )

    assert third["analysis"] == "어긋남"
    assert third["outcome"] == "design_flawed"
    assert third["procedure"] == "1. 시료를 냉각한다\n2. 저항을 측정한다"  # 2단계 값도 여전히 보임
    assert third["experiment_results"] == "저항이 거의 안 변했다"
    # analyze_results가 남긴 갈래별 안내가 뒤이은 find_operation_references에 덮어써지지
    # 않고 앞부분에 그대로 남아 있어야 한다.
    assert third["comment"].startswith("실험 설계에 문제가 있어 보입니다")

    # report 단계는 LLM 호출이 없으므로 몽키패치를 안 갈아끼워도 된다 — invoke_with_fallback이
    # 실제로 안 불린다는 것 자체가 이 전환의 검증 포인트.
    fourth = app.invoke({"stage": "report"}, config=config)

    assert "가설X" in fourth["experiment_report"]  # 1단계 값
    assert "1. 시료를 냉각한다" in fourth["experiment_report"]  # 2단계 값
    assert "어긋남" in fourth["experiment_report"]  # 3단계 값
    assert "설계 결함으로 추정" in fourth["experiment_report"]  # outcome 라벨


# --- check_equipment_precautions() (안전 가드레일, 08-02) ----------------------


def test_check_equipment_precautions_prepends_matching_equipment_warning(monkeypatch):
    monkeypatch.setattr(
        equipment, "list_equipment",
        lambda **kw: [{"id": 1, "name": "오실로스코프", "purpose": "", "detail": "", "precautions": "전압 정격 초과 금지"}],
    )

    state = research_workflow.WorkflowState(
        topic="주제", equipment_needed="오실로스코프, 온도 조절 장치", comment="기존 안내",
    )
    result = research_workflow.check_equipment_precautions(state)

    assert "오실로스코프" in result["comment"]
    assert "전압 정격 초과 금지" in result["comment"]
    assert result["comment"].endswith("기존 안내")  # 기존 comment는 안 지우고 뒤에 유지


def test_check_equipment_precautions_ignores_equipment_not_mentioned(monkeypatch):
    monkeypatch.setattr(
        equipment, "list_equipment",
        lambda **kw: [{"id": 1, "name": "레이저", "purpose": "", "detail": "", "precautions": "눈에 직접 노출 금지"}],
    )

    state = research_workflow.WorkflowState(topic="주제", equipment_needed="오실로스코프만 사용")
    result = research_workflow.check_equipment_precautions(state)

    assert result == {}  # 언급 안 된 장비의 주의사항은 안 붙음


def test_check_equipment_precautions_ignores_equipment_without_precautions(monkeypatch):
    monkeypatch.setattr(
        equipment, "list_equipment",
        lambda **kw: [{"id": 1, "name": "오실로스코프", "purpose": "", "detail": "", "precautions": ""}],
    )

    state = research_workflow.WorkflowState(topic="주제", equipment_needed="오실로스코프 사용")
    result = research_workflow.check_equipment_precautions(state)

    assert result == {}  # 주의사항이 비어있으면 붙일 게 없음


def test_check_equipment_precautions_ignores_equipment_with_empty_name(monkeypatch):
    # 이름이 빈 문자열이면 `"" in 아무거나`가 항상 True라 모든 설계에 이 주의사항이
    # 붙는다 — name 컬럼이 NOT NULL이어도 ""는 통과하므로 실제로 가능한 상태다.
    monkeypatch.setattr(
        equipment, "list_equipment",
        lambda **kw: [{"id": 1, "name": "", "purpose": "", "detail": "", "precautions": "이름 없는 장비 주의"}],
    )

    state = research_workflow.WorkflowState(topic="주제", equipment_needed="오실로스코프")
    result = research_workflow.check_equipment_precautions(state)

    assert result == {}


def test_check_equipment_precautions_matches_equipment_name_as_substring(monkeypatch):
    # 부분 문자열 매칭은 의도된 동작 — 설계가 장비를 수식어와 함께 부르는 게 정상이다.
    monkeypatch.setattr(
        equipment, "list_equipment",
        lambda **kw: [{"id": 1, "name": "오실로스코프", "purpose": "", "detail": "", "precautions": "정격 초과 금지"}],
    )

    state = research_workflow.WorkflowState(topic="주제", equipment_needed="디지털 오실로스코프 2채널")
    result = research_workflow.check_equipment_precautions(state)

    assert "정격 초과 금지" in result["comment"]


def test_check_equipment_precautions_returns_empty_when_no_equipment_registered(monkeypatch):
    monkeypatch.setattr(equipment, "list_equipment", lambda **kw: [])

    state = research_workflow.WorkflowState(topic="주제", equipment_needed="아무거나")
    result = research_workflow.check_equipment_precautions(state)

    assert result == {}
