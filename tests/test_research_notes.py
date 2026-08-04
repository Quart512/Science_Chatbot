"""
research_notes.py — 연구 워크플로우 단계별 메모 RDB(SQLite).
test_research_branches.py와 같은 패턴(":memory:" 연결 + init_schema() 명시 호출).
"""
import sqlite3

import pytest

import research_notes


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    research_notes.init_schema(c)
    yield c
    c.close()


def test_get_notes_empty_when_none_saved(conn):
    assert research_notes.get_notes_for_checkpoints(["c1"], conn=conn) == {}


def test_set_note_then_get_returns_it(conn):
    research_notes.set_note("c1", "t1", "장비를 다시 확인할 것", conn=conn)
    assert research_notes.get_notes_for_checkpoints(["c1"], conn=conn) == {"c1": "장비를 다시 확인할 것"}


def test_set_note_overwrites_existing(conn):
    research_notes.set_note("c1", "t1", "첫 메모", conn=conn)
    research_notes.set_note("c1", "t1", "고친 메모", conn=conn)
    assert research_notes.get_notes_for_checkpoints(["c1"], conn=conn) == {"c1": "고친 메모"}


def test_set_note_with_empty_string_deletes_row(conn):
    research_notes.set_note("c1", "t1", "메모", conn=conn)
    research_notes.set_note("c1", "t1", "", conn=conn)
    assert research_notes.get_notes_for_checkpoints(["c1"], conn=conn) == {}


def test_set_note_with_whitespace_only_deletes_row(conn):
    research_notes.set_note("c1", "t1", "메모", conn=conn)
    research_notes.set_note("c1", "t1", "   \n  ", conn=conn)
    assert research_notes.get_notes_for_checkpoints(["c1"], conn=conn) == {}


def test_set_note_on_nonexistent_row_with_empty_string_is_noop(conn):
    research_notes.set_note("c1", "t1", "", conn=conn)
    assert research_notes.get_notes_for_checkpoints(["c1"], conn=conn) == {}


def test_get_notes_only_returns_requested_ids(conn):
    research_notes.set_note("c1", "t1", "메모1", conn=conn)
    research_notes.set_note("c2", "t1", "메모2", conn=conn)
    assert research_notes.get_notes_for_checkpoints(["c1"], conn=conn) == {"c1": "메모1"}


def test_get_notes_returns_empty_for_empty_input(conn):
    assert research_notes.get_notes_for_checkpoints([], conn=conn) == {}
