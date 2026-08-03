# 실험도구 저장소(⑤) — RDB(SQLite). interests.py/paper_catalog.py와 같은 data/app.db를
# 다른 테이블로 공유(RoadMap "VDB vs RDB — 관심사·실험도구는 RDB로" 참고) — 경로 상수만
# 참조하고 스키마 적용은 각자 한다(paper_catalog.py와 같은 이유: 재사용하면 이 연결을
# 열 때마다 interests 마이그레이션까지 딸려와 책임이 섞인다).
#
# 스키마는 name(장비명)/purpose(목적)/detail(세부내용) 자유 텍스트 3필드다. RoadMap이
# 애초에 RDB를 고른 예시 근거는 "측정 범위 X 이상" 같은 숫자 범위 SQL 조회였지만, 실제
# 착수 시점(08-02)에 스펙 세부는 detail 자유 텍스트로 몰고 purpose만 조회에 쓰기로
# 결정했다 — 연구 워크플로우가 장비를 찾을 땐 purpose를 LLM에게 읽혀 판단하게 한다
# (SQL WHERE 범위 조건이 아니라 RoadMap의 다른 근거 "목록이 짧으니 프롬프트에 넣으면
# 된다"쪽 방식). 구조화된 숫자 필드(예: min/max 측정 범위 컬럼)로 진짜 SQL 범위 조회가
# 필요해지면 그때 detail에서 분리해 추가한다(단순 경로부터).

import os
import sqlite3
from datetime import datetime, timezone

import interests

APP_DB_PATH = interests.APP_DB_PATH

_UPDATABLE_FIELDS = ("name", "purpose", "detail")

SCHEMA = """
CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def _get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(APP_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_equipment(
    name: str,
    purpose: str = "",
    detail: str = "",
    *,
    conn: sqlite3.Connection | None = None,
) -> int:
    """장비 하나를 등록하고 새 id를 반환한다. conn을 안 넘기면 이 함수가 알아서 열고 닫는다."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        now = _now()
        cur = conn.execute(
            "INSERT INTO equipment (name, purpose, detail, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (name, purpose, detail, now, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        if owns_conn:
            conn.close()


def list_equipment(*, conn: sqlite3.Connection | None = None) -> list[dict]:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        rows = conn.execute("SELECT * FROM equipment ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


def get_equipment(equipment_id: int, *, conn: sqlite3.Connection | None = None) -> dict | None:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        row = conn.execute("SELECT * FROM equipment WHERE id = ?", (equipment_id,)).fetchone()
        return dict(row) if row else None
    finally:
        if owns_conn:
            conn.close()


def update_equipment(equipment_id: int, *, conn: sqlite3.Connection | None = None, **fields) -> bool:
    """주어진 필드만 부분 갱신한다(interests.update_interest와 같은 계약) — 반환값은
    실제로 갱신된 행이 있었는지. _UPDATABLE_FIELDS 밖의 키는 ValueError(필드명이 SQL에
    f-string으로 들어가므로 이 화이트리스트가 인젝션 방지도 겸함)."""
    unknown = set(fields) - set(_UPDATABLE_FIELDS)
    if unknown:
        raise ValueError(f"업데이트할 수 없는 필드: {unknown}")
    if not fields:
        return False

    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        set_clause = ", ".join(f"{k} = ?" for k in fields) + ", updated_at = ?"
        values = [*fields.values(), _now(), equipment_id]
        cur = conn.execute(f"UPDATE equipment SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


def delete_equipment(equipment_id: int, *, conn: sqlite3.Connection | None = None) -> bool:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute("DELETE FROM equipment WHERE id = ?", (equipment_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    # 수동 스모크 테스트 — 실제 data/app.db에 씀
    new_id = create_equipment(
        name="오실로스코프",
        purpose="전기 신호의 시간에 따른 파형 관찰",
        detail="대역폭 100MHz, 2채널",
    )
    print(f"등록됨: id={new_id}")
    print(get_equipment(new_id))
