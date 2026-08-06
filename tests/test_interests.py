"""
interests.py — 관심사 RDB(SQLite) CRUD. FakeVectorstore 같은 가짜가 필요 없다 —
sqlite3의 ":memory:" 연결이 진짜 DB라 밀리초 단위로 돈다. init_schema()를 명시적으로
불러야 하는 이유는 interests.py 모듈 docstring 참고(_get_connection()을 안 거치므로).
"""
import sqlite3

import pytest

import interests


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    interests.init_schema(c)
    yield c
    c.close()


def test_create_interest_returns_new_id(conn):
    interest_id = interests.create_interest("양자컴퓨팅", conn=conn)
    assert interest_id == 1


def test_create_interest_stores_all_fields(conn):
    interest_id = interests.create_interest(
        "양자컴퓨팅",
        looking_for="오류 정정 동향",
        already_known="큐비트 기본",
        excluded_topics="양자 화학",
        conn=conn,
    )
    row = interests.get_interest(interest_id, conn=conn)
    assert row["title"] == "양자컴퓨팅"
    assert row["looking_for"] == "오류 정정 동향"
    assert row["already_known"] == "큐비트 기본"
    assert row["excluded_topics"] == "양자 화학"
    assert row["created_at"] == row["updated_at"]  # 생성 직후엔 두 값이 같아야 함


def test_create_interest_defaults_template_fields_to_empty_string(conn):
    interest_id = interests.create_interest("제목만", conn=conn)
    row = interests.get_interest(interest_id, conn=conn)
    assert row["looking_for"] == ""
    assert row["already_known"] == ""
    assert row["excluded_topics"] == ""


def test_get_interest_returns_none_when_not_found(conn):
    assert interests.get_interest(999, conn=conn) is None


def test_list_interests_returns_in_id_order(conn):
    interests.create_interest("첫번째", conn=conn)
    interests.create_interest("두번째", conn=conn)
    interests.create_interest("세번째", conn=conn)

    rows = interests.list_interests(conn=conn)
    assert [r["title"] for r in rows] == ["첫번째", "두번째", "세번째"]


def test_move_interest_swaps_with_neighbor(conn):
    first = interests.create_interest("첫번째", conn=conn)
    second = interests.create_interest("두번째", conn=conn)

    assert interests.move_interest(second, "up", conn=conn) is True
    rows = interests.list_interests(conn=conn)
    assert [r["title"] for r in rows] == ["두번째", "첫번째"]
    assert interests.move_interest(first, "down", conn=conn) is False  # 이미 맨 뒤


def test_update_interest_only_touches_given_fields(conn):
    interest_id = interests.create_interest(
        "원래 제목", looking_for="원래 내용", already_known="아는 것", conn=conn
    )
    updated = interests.update_interest(interest_id, title="바뀐 제목", conn=conn)

    row = interests.get_interest(interest_id, conn=conn)
    assert updated is True
    assert row["title"] == "바뀐 제목"
    assert row["looking_for"] == "원래 내용"  # 안 건드린 필드는 그대로
    assert row["already_known"] == "아는 것"


def test_update_interest_bumps_updated_at_but_not_created_at(conn):
    interest_id = interests.create_interest("제목", conn=conn)
    before = interests.get_interest(interest_id, conn=conn)

    interests.update_interest(interest_id, title="새 제목", conn=conn)

    after = interests.get_interest(interest_id, conn=conn)
    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] >= before["updated_at"]


def test_update_interest_returns_false_when_id_not_found(conn):
    assert interests.update_interest(999, title="유령", conn=conn) is False


def test_update_interest_rejects_unknown_field(conn):
    interest_id = interests.create_interest("제목", conn=conn)
    with pytest.raises(ValueError):
        interests.update_interest(interest_id, titel="오타", conn=conn)  # noqa: 의도된 오타


def test_update_interest_with_no_fields_returns_false(conn):
    interest_id = interests.create_interest("제목", conn=conn)
    assert interests.update_interest(interest_id, conn=conn) is False


def test_delete_interest_removes_row(conn):
    interest_id = interests.create_interest("제목", conn=conn)
    assert interests.delete_interest(interest_id, conn=conn) is True
    assert interests.get_interest(interest_id, conn=conn) is None


def test_delete_interest_returns_false_when_id_not_found(conn):
    assert interests.delete_interest(999, conn=conn) is False


def test_delete_interest_does_not_touch_other_rows(conn):
    keep_id = interests.create_interest("남길 것", conn=conn)
    delete_id = interests.create_interest("지울 것", conn=conn)
    interests.delete_interest(delete_id, conn=conn)
    assert interests.get_interest(keep_id, conn=conn) is not None
    assert [r["id"] for r in interests.list_interests(conn=conn)] == [keep_id]
