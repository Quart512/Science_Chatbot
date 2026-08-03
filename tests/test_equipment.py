"""
equipment.py — 실험도구 RDB(SQLite) CRUD (⑤). interests.py와 완전히 같은 패턴이라
테스트 구조도 그대로 따른다(:memory: 연결, init_schema() 명시 호출 — 이유는
equipment.py 모듈 docstring 및 interests.py 참고).
"""
import sqlite3

import pytest

import equipment


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    equipment.init_schema(c)
    yield c
    c.close()


def test_create_equipment_returns_new_id(conn):
    equipment_id = equipment.create_equipment("오실로스코프", conn=conn)
    assert equipment_id == 1


def test_create_equipment_stores_all_fields(conn):
    equipment_id = equipment.create_equipment(
        "오실로스코프",
        purpose="전기 신호 파형 관찰",
        detail="대역폭 100MHz, 2채널",
        conn=conn,
    )
    row = equipment.get_equipment(equipment_id, conn=conn)
    assert row["name"] == "오실로스코프"
    assert row["purpose"] == "전기 신호 파형 관찰"
    assert row["detail"] == "대역폭 100MHz, 2채널"
    assert row["created_at"] == row["updated_at"]  # 생성 직후엔 두 값이 같아야 함


def test_create_equipment_defaults_purpose_and_detail_to_empty_string(conn):
    equipment_id = equipment.create_equipment("이름만", conn=conn)
    row = equipment.get_equipment(equipment_id, conn=conn)
    assert row["purpose"] == ""
    assert row["detail"] == ""


def test_get_equipment_returns_none_when_not_found(conn):
    assert equipment.get_equipment(999, conn=conn) is None


def test_list_equipment_returns_in_id_order(conn):
    equipment.create_equipment("첫번째", conn=conn)
    equipment.create_equipment("두번째", conn=conn)
    equipment.create_equipment("세번째", conn=conn)

    rows = equipment.list_equipment(conn=conn)
    assert [r["name"] for r in rows] == ["첫번째", "두번째", "세번째"]


def test_update_equipment_only_touches_given_fields(conn):
    equipment_id = equipment.create_equipment(
        "원래 이름", purpose="원래 목적", detail="원래 세부", conn=conn
    )
    updated = equipment.update_equipment(equipment_id, name="바뀐 이름", conn=conn)

    row = equipment.get_equipment(equipment_id, conn=conn)
    assert updated is True
    assert row["name"] == "바뀐 이름"
    assert row["purpose"] == "원래 목적"  # 안 건드린 필드는 그대로
    assert row["detail"] == "원래 세부"


def test_update_equipment_bumps_updated_at_but_not_created_at(conn):
    equipment_id = equipment.create_equipment("이름", conn=conn)
    before = equipment.get_equipment(equipment_id, conn=conn)

    equipment.update_equipment(equipment_id, name="새 이름", conn=conn)

    after = equipment.get_equipment(equipment_id, conn=conn)
    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] >= before["updated_at"]


def test_update_equipment_returns_false_when_id_not_found(conn):
    assert equipment.update_equipment(999, name="유령", conn=conn) is False


def test_update_equipment_rejects_unknown_field(conn):
    equipment_id = equipment.create_equipment("이름", conn=conn)
    with pytest.raises(ValueError):
        equipment.update_equipment(equipment_id, nmae="오타", conn=conn)  # noqa: 의도된 오타


def test_update_equipment_with_no_fields_returns_false(conn):
    equipment_id = equipment.create_equipment("이름", conn=conn)
    assert equipment.update_equipment(equipment_id, conn=conn) is False


def test_delete_equipment_removes_row(conn):
    equipment_id = equipment.create_equipment("이름", conn=conn)
    assert equipment.delete_equipment(equipment_id, conn=conn) is True
    assert equipment.get_equipment(equipment_id, conn=conn) is None


def test_delete_equipment_returns_false_when_id_not_found(conn):
    assert equipment.delete_equipment(999, conn=conn) is False


def test_delete_equipment_does_not_touch_other_rows(conn):
    keep_id = equipment.create_equipment("남길 것", conn=conn)
    delete_id = equipment.create_equipment("지울 것", conn=conn)
    equipment.delete_equipment(delete_id, conn=conn)
    assert equipment.get_equipment(keep_id, conn=conn) is not None
    assert [r["id"] for r in equipment.list_equipment(conn=conn)] == [keep_id]
