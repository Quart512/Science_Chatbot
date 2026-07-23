"""
route_by_fix — graph.py의 순수 함수. State만 보고 다음 노드를 결정하고,
LLM·tool·벡터DB를 전혀 건드리지 않는다. 그래서 모킹이 필요 없다
(retrieval의 import-time 부작용은 conftest.py에서 이미 처리됨).

route_by_fix의 분기 3가지:
    1. fix_needed가 False거나 try_count가 limit에 도달 -> final_answer
    2. fix_needed=True + needs_more_context=True         -> retrieve
    3. fix_needed=True + needs_more_context=False         -> generate

make_state는 conftest.py의 fixture(모든 테스트 파일이 공유) — 여기선 따로 정의 안 함.
"""
from graph import route_by_fix


def test_no_fix_needed_goes_to_final_answer(make_state):
    state = make_state(fix_needed=False)
    assert route_by_fix(state) == "final_answer"


def test_limit_reached_goes_to_final_answer_even_if_fix_needed(make_state):
    # fix_needed=True라도 try_count가 limit에 도달했으면 강제 종료
    state = make_state(fix_needed=True, try_count=4, limit=4)
    assert route_by_fix(state) == "final_answer"


def test_fix_needed_with_more_context_goes_to_retrieve(make_state):
    state = make_state(fix_needed=True, try_count=0, limit=4, needs_more_context=True)
    assert route_by_fix(state) == "retrieve"


def test_fix_needed_without_more_context_goes_to_generate(make_state):
    state = make_state(fix_needed=True, try_count=0, limit=4, needs_more_context=False)
    assert route_by_fix(state) == "generate"
