"""
reset_turn — graph.py의 순수 함수. 멀티턴 경계에서 임시 상태를 초기화한다.
State 필드 자체의 타입·제약은 Pydantic이 이미 보장하므로 여기선 테스트 안 함.
대신 "reset_turn이 State를 올바르게 다루는가"만 검증한다:
    1. 초기화 대상 필드들이 실제로 기본값으로 돌아오는가
    2. messages는 절대 건드리지 않는가 (add_messages reducer가 누적하도록 보존돼야 함)
    3. 리턴하는 dict의 키가 전부 실제 State 필드 이름과 일치하는가
       (필드 이름 오타나, State에 새 필드 추가 후 reset_turn 갱신을 깜빡한 경우를 잡는 안전망)
"""
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

from graph import State, reset_turn

EXPECTED_RESET = {
    "context": [],
    "answer": "",
    "comment": "",
    "tokens_used": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    "fix_needed": False,
    "what_to_fix": "",
    "needs_more_context": False,
    "try_count": 0,
    "generated_by": "",
    "disabled_models": [],
    "tool_rounds": 0,
    "tool_failures": {},
    "disabled_tools": [],
    "turn_start_len": 0,
}


def test_reset_turn_clears_transient_fields(make_state):
    dirty_state = make_state(
        context=[Document(page_content="이전 검색 결과")],
        answer="이전 답",
        comment="이전 코멘트",
        tokens_used={"input_tokens": 5, "output_tokens": 5, "total_tokens": 10},
        fix_needed=True,
        what_to_fix="뭔가 고쳐야 함",
        needs_more_context=True,
        try_count=3,
        generated_by="claude",
        disabled_models=["claude"],
        tool_rounds=2,
        tool_failures={"search_wikipedia": 1},
        disabled_tools=["search_wikipedia"],
    )

    assert reset_turn(dirty_state) == EXPECTED_RESET


def test_reset_turn_is_idempotent_on_fresh_state(make_state):
    # 이미 초기값인 State에 다시 적용해도 결과는 동일해야 함
    fresh_state = make_state()
    assert reset_turn(fresh_state) == EXPECTED_RESET


def test_reset_turn_does_not_touch_messages(make_state):
    # messages는 멀티턴 대화 이력이라 reset 대상이 아님 — 리턴 dict에 키 자체가 없어야
    # add_messages reducer가 "덮어쓰기"가 아니라 "누적"으로 계속 동작함
    state = make_state(messages=[HumanMessage(content="이전 질문")])
    assert "messages" not in reset_turn(state)


def test_reset_turn_records_turn_start_len(make_state):
    # turn_start_len은 고정값 0이 아니라 "이번 턴 시작 시점의 messages 길이"를 기록해야 함 —
    # final_answer가 이걸 경계로 이번 턴 메시지만 정리(RemoveMessage)하므로 실제로 안 맞으면
    # 이전 턴 대화 이력까지 같이 지워지는 사고로 이어짐
    state = make_state(messages=[HumanMessage(content="이전 질문1"), HumanMessage(content="이전 질문2")])
    assert reset_turn(state)["turn_start_len"] == 2


def test_reset_turn_returns_only_known_state_fields(make_state):
    # 필드 이름 오타, 또는 State에 필드를 추가하고 reset_turn 갱신을 깜빡한 경우를 잡는 안전망.
    # (Pydantic이 보장 못 해주는 부분 — reset_turn은 State가 아니라 그냥 dict를 리턴하므로)
    state = make_state()
    reset_keys = set(reset_turn(state).keys())
    assert reset_keys <= set(State.model_fields.keys())
