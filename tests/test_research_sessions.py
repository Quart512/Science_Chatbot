"""
research_sessions.py — 연구 세션 목록 RDB(SQLite) CRUD. test_interests.py와 같은
패턴(":memory:" 연결 + init_schema() 명시 호출) — 차이는 PK가 thread_id라
create_session()이 새 id를 반환하지 않고 호출자가 넘긴 값을 그대로 쓴다는 점.
"""
import sqlite3

import pytest

import research_sessions


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    research_sessions.init_schema(c)
    yield c
    c.close()


def test_create_session_stores_all_fields(conn):
    research_sessions.create_session(
        "thread-1", title="제목", topic="양자컴퓨팅 오류 정정", conn=conn
    )
    row = research_sessions.get_session("thread-1", conn=conn)
    assert row["thread_id"] == "thread-1"
    assert row["title"] == "제목"
    assert row["topic"] == "양자컴퓨팅 오류 정정"
    assert row["stage"] == "hypothesis"  # 기본값
    assert row["created_at"] == row["updated_at"]


def test_create_session_accepts_explicit_stage(conn):
    research_sessions.create_session(
        "thread-1", title="제목", topic="주제", stage="design", conn=conn
    )
    row = research_sessions.get_session("thread-1", conn=conn)
    assert row["stage"] == "design"


def test_get_session_returns_none_when_not_found(conn):
    assert research_sessions.get_session("no-such-thread", conn=conn) is None


def test_list_sessions_returns_in_creation_order(conn):
    research_sessions.create_session("t1", title="첫번째", topic="주제1", conn=conn)
    research_sessions.create_session("t2", title="두번째", topic="주제2", conn=conn)
    research_sessions.create_session("t3", title="세번째", topic="주제3", conn=conn)

    rows = research_sessions.list_sessions(conn=conn)
    assert [r["title"] for r in rows] == ["첫번째", "두번째", "세번째"]


def test_update_title_only_touches_title(conn):
    research_sessions.create_session("t1", title="원래 제목", topic="주제", stage="design", conn=conn)
    updated = research_sessions.update_title("t1", "바뀐 제목", conn=conn)

    row = research_sessions.get_session("t1", conn=conn)
    assert updated is True
    assert row["title"] == "바뀐 제목"
    assert row["topic"] == "주제"  # 안 건드린 필드는 그대로
    assert row["stage"] == "design"


def test_update_title_returns_false_when_not_found(conn):
    assert research_sessions.update_title("no-such-thread", "새 제목", conn=conn) is False


def test_update_stage_only_touches_stage(conn):
    research_sessions.create_session("t1", title="제목", topic="주제", conn=conn)
    updated = research_sessions.update_stage("t1", "operation", conn=conn)

    row = research_sessions.get_session("t1", conn=conn)
    assert updated is True
    assert row["stage"] == "operation"
    assert row["title"] == "제목"


def test_update_stage_returns_false_when_not_found(conn):
    assert research_sessions.update_stage("no-such-thread", "design", conn=conn) is False


def test_update_bumps_updated_at_but_not_created_at(conn):
    research_sessions.create_session("t1", title="제목", topic="주제", conn=conn)
    before = research_sessions.get_session("t1", conn=conn)

    research_sessions.update_stage("t1", "design", conn=conn)

    after = research_sessions.get_session("t1", conn=conn)
    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] >= before["updated_at"]


def test_delete_session_removes_row(conn):
    research_sessions.create_session("t1", title="제목", topic="주제", conn=conn)
    assert research_sessions.delete_session("t1", conn=conn) is True
    assert research_sessions.get_session("t1", conn=conn) is None


def test_delete_session_returns_false_when_not_found(conn):
    assert research_sessions.delete_session("no-such-thread", conn=conn) is False


def test_delete_session_does_not_touch_other_rows(conn):
    research_sessions.create_session("keep", title="남길 것", topic="주제", conn=conn)
    research_sessions.create_session("drop", title="지울 것", topic="주제", conn=conn)
    research_sessions.delete_session("drop", conn=conn)
    assert research_sessions.get_session("keep", conn=conn) is not None
    assert [r["thread_id"] for r in research_sessions.list_sessions(conn=conn)] == ["keep"]
