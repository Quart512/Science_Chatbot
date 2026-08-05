# run_tools() — graph.py의 tool 실행 노드. 실제 tool(DDG/arxiv/wikipedia)·네트워크
# 없이 tool_map을 가짜로 갈아끼워 조립 로직(성공/실패 분기, 서킷 브레이커, 관측성
# 필드 tools_used/tool_errors, 타임아웃 wrapper)만 검증한다.

import concurrent.futures
import time

from langchain_core.messages import AIMessage

import graph
from graph import _invoke_tool_with_timeout, run_tools


class FakeTool:
    """tool_map[name]이 실제로 노출하는 표면(.invoke(args))만 흉내낸다."""

    def __init__(self, fn):
        self._fn = fn

    def invoke(self, args):
        return self._fn(args)


def _state_with_tool_call(make_state, name: str, **overrides):
    msg = AIMessage(content="", tool_calls=[{"name": name, "args": {"query": "q"}, "id": "call-1"}])
    return make_state(messages=[msg], **overrides)


def test_successful_call_appends_tools_used_and_resets_failures(make_state, monkeypatch):
    monkeypatch.setitem(graph.tool_map, "fake", FakeTool(lambda args: "결과 문자열"))
    state = _state_with_tool_call(make_state, "fake", tool_failures={"fake": 1})

    result = run_tools(state)

    assert result["tools_used"] == ["fake"]
    assert result["tool_errors"] == []
    assert result["tool_failures"]["fake"] == 0  # 성공하면 연속 실패 카운트 리셋
    assert result["tool_rounds"] == 1  # 실제로 시도했으므로 라운드 소모
    assert result["messages"][0].content == "결과 문자열"


def test_exception_appends_tool_errors_and_disables_after_two_failures(make_state, monkeypatch):
    def _boom(args):
        raise ValueError("네트워크 오류")
    monkeypatch.setitem(graph.tool_map, "fake", FakeTool(_boom))
    state = _state_with_tool_call(make_state, "fake", tool_failures={"fake": 1})  # 이미 1회 실패

    result = run_tools(state)

    assert result["tool_errors"] == ["fake: ValueError"]
    assert result["tool_failures"]["fake"] == 2
    assert "fake" in result["disabled_tools"]  # 연속 2회로 서킷 브레이커 발동
    assert result["messages"][0].status == "error"
    assert "[호출 실패]" in result["messages"][0].content


def test_timeout_appends_tool_errors_with_timeout_label(make_state, monkeypatch):
    # 실제 15초를 기다리지 않고 _invoke_tool_with_timeout 자체를 갈아끼워 타임아웃
    # 분기만 검증 — 진짜 타임아웃 동작은 아래 test_invoke_tool_with_timeout_raises에서 확인.
    monkeypatch.setitem(graph.tool_map, "fake", FakeTool(lambda args: "안 씀"))
    monkeypatch.setattr(
        graph, "_invoke_tool_with_timeout",
        lambda tool, args: (_ for _ in ()).throw(concurrent.futures.TimeoutError()),
    )
    state = _state_with_tool_call(make_state, "fake")

    result = run_tools(state)

    assert result["tool_errors"] == ["fake: TimeoutError"]
    assert "[시간 초과]" in result["messages"][0].content
    assert result["messages"][0].status == "error"


def test_empty_result_does_not_count_as_error(make_state, monkeypatch):
    monkeypatch.setitem(graph.tool_map, "fake", FakeTool(lambda args: ""))
    state = _state_with_tool_call(make_state, "fake")

    result = run_tools(state)

    assert result["tool_errors"] == []
    assert result["tools_used"] == []  # 빈 결과는 성공으로 안 침
    assert "[결과 없음]" in result["messages"][0].content


def test_invoke_tool_with_timeout_raises_when_tool_hangs():
    # 진짜 시간 초과 동작 확인 — 스레드에서 도는 tool이 timeout보다 오래 걸리면
    # concurrent.futures.TimeoutError가 나야 한다(스레드 자체는 못 죽이지만 무해).
    slow_tool = FakeTool(lambda args: time.sleep(0.3) or "완료")
    try:
        _invoke_tool_with_timeout(slow_tool, {}, timeout=0.05)
        assert False, "TimeoutError가 났어야 한다"
    except concurrent.futures.TimeoutError:
        pass


def test_invoke_tool_with_timeout_returns_result_when_fast_enough():
    fast_tool = FakeTool(lambda args: "빠른 결과")
    assert _invoke_tool_with_timeout(fast_tool, {}, timeout=5) == "빠른 결과"
