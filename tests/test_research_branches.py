"""
research_branches.py — 연구 워크플로우 체크포인트 분기 기록 RDB(SQLite).
test_research_sessions.py와 같은 패턴(":memory:" 연결 + init_schema() 명시 호출).
"""
import sqlite3

import pytest

import research_branches


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    research_branches.init_schema(c)
    yield c
    c.close()


def test_get_sources_empty_when_no_branches_recorded(conn):
    assert research_branches.get_sources(["c1", "c2"], conn=conn) == {}


def test_get_sources_returns_recorded_mapping(conn):
    research_branches.record_branch("c2", "c1", thread_id="t1", conn=conn)
    assert research_branches.get_sources(["c1", "c2"], conn=conn) == {"c2": "c1"}


def test_get_sources_only_returns_requested_ids(conn):
    research_branches.record_branch("c2", "c1", thread_id="t1", conn=conn)
    research_branches.record_branch("c4", "c3", thread_id="t1", conn=conn)
    assert research_branches.get_sources(["c2"], conn=conn) == {"c2": "c1"}


def test_get_sources_returns_empty_for_empty_input(conn):
    # 히스토리가 아예 없을 때(entries=[])도 IN () SQL 오류 없이 빈 dict를 내야 한다.
    assert research_branches.get_sources([], conn=conn) == {}


def test_record_branch_overwrites_existing_child(conn):
    # INSERT OR REPLACE — 같은 child_checkpoint_id로 다시 기록하면(이론상 안 생겨야
    # 하지만) 최신 값으로 덮어써야지 UNIQUE 제약 오류가 나면 안 된다.
    research_branches.record_branch("c2", "c1", thread_id="t1", conn=conn)
    research_branches.record_branch("c2", "c0", thread_id="t1", conn=conn)
    assert research_branches.get_sources(["c2"], conn=conn) == {"c2": "c0"}
