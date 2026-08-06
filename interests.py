# 관심사 저장소(①) — RDB(SQLite). 필드 단위 수정이 흔하고 논문 카탈로그와 조인이
# 필요해서 VDB 대신 RDB로 결정(RoadMap "VDB vs RDB" 참고). data/app.db에 저장 —
# 체크포인트 DB와 파일은 분리하되 같은 data/ 디렉터리 공유. 테이블 하나뿐이라
# ORM 없이 표준 라이브러리 sqlite3(단순 경로부터).

import os
import sqlite3
from datetime import datetime, timezone

import library_order

APP_DB_PATH = "data/app.db"

# 로드맵이 명시한 필수 템플릿 필드 — 관심사 문서는 이 세 질문에 대한 답이 전부다
# (①b 관련도 판정 정확도가 여기 달려 있다는 게 로드맵의 근거).
_UPDATABLE_FIELDS = ("title", "looking_for", "already_known", "excluded_topics")

SCHEMA = """
CREATE TABLE IF NOT EXISTS interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    looking_for TEXT NOT NULL DEFAULT '',
    already_known TEXT NOT NULL DEFAULT '',
    excluded_topics TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# sort_order(08-06, 라이브러리 화면 수동 정렬 — library_order.py 참고) — 처음으로 이
# 테이블에 컬럼을 추가하는 경우라 equipment.py/paper_catalog.py의 기존 ALTER TABLE
# 패턴을 그대로 들여온다("정식 마이그레이션 도구는 과하다"는 원래 판단은 테이블이
# 하나면 유지되지만, 컬럼 추가 자체는 피할 수 없다).
_EXPECTED_COLUMNS = {
    "sort_order": "INTEGER NOT NULL DEFAULT 0",
}


def init_schema(conn: sqlite3.Connection) -> None:
    """테이블이 없으면 만든다(CREATE TABLE IF NOT EXISTS라 여러 번 불러도 안전) — 정식
    마이그레이션 도구는 테이블이 하나뿐인 지금은 과하다(단순 경로부터). conn을 인자로
    받는 이유: 실제 연결(_get_connection())과 테스트용 :memory: 연결 양쪽에 같은 스키마를
    적용해야 하는데, 후자는 _get_connection()을 거치지 않으므로 명시적으로 호출해야 한다."""
    conn.executescript(SCHEMA)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(interests)")}
    for name, ddl in _EXPECTED_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE interests ADD COLUMN {name} {ddl}")
            if name == "sort_order":
                library_order.backfill_sort_order("interests", "id", conn=conn)
    conn.commit()


def _get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(APP_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row  # dict처럼 컬럼명으로 접근(list(row) 대신 row["title"])
    init_schema(conn)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_interest(
    title: str,
    looking_for: str = "",
    already_known: str = "",
    excluded_topics: str = "",
    *,
    conn: sqlite3.Connection | None = None,
) -> int:
    """관심사 하나를 등록하고 새 id를 반환한다. conn을 안 넘기면 이 함수가 알아서 열고 닫는다."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        now = _now()
        sort_order = library_order.next_sort_order("interests", conn=conn)
        cur = conn.execute(
            "INSERT INTO interests (title, looking_for, already_known, excluded_topics, sort_order, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, looking_for, already_known, excluded_topics, sort_order, now, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        if owns_conn:
            conn.close()


def list_interests(*, conn: sqlite3.Connection | None = None) -> list[dict]:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        rows = conn.execute("SELECT * FROM interests ORDER BY sort_order").fetchall()
        return [dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


def move_interest(interest_id: int, direction: str, *, conn: sqlite3.Connection | None = None) -> bool:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        return library_order.move_item("interests", "id", interest_id, direction, conn=conn)
    finally:
        if owns_conn:
            conn.close()


def get_interest(interest_id: int, *, conn: sqlite3.Connection | None = None) -> dict | None:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        row = conn.execute("SELECT * FROM interests WHERE id = ?", (interest_id,)).fetchone()
        return dict(row) if row else None
    finally:
        if owns_conn:
            conn.close()


def update_interest(interest_id: int, *, conn: sqlite3.Connection | None = None, **fields) -> bool:
    """주어진 필드만 부분 갱신한다. 반환값은 실제로 갱신된 행이 있었는지(없는 id는
    조용히 무시하지 않고 알린다). _UPDATABLE_FIELDS 밖의 키는 ValueError — 필드명이
    SQL에 f-string으로 들어가므로 이 화이트리스트가 인젝션 방지도 겸한다."""
    unknown = set(fields) - set(_UPDATABLE_FIELDS)
    if unknown:
        raise ValueError(f"업데이트할 수 없는 필드: {unknown}")
    if not fields:
        return False

    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        set_clause = ", ".join(f"{k} = ?" for k in fields) + ", updated_at = ?"
        values = [*fields.values(), _now(), interest_id]
        cur = conn.execute(f"UPDATE interests SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


def delete_interest(interest_id: int, *, conn: sqlite3.Connection | None = None) -> bool:
    """관심사를 삭제한다(반환값은 실제로 지워졌는지 — update_interest()와 같은 계약).
    이 행 하나만 지운다 — interest_paper 조인 행(paper_catalog.py가 스키마 소유)은
    여기서 안 지운다. 순환 import(paper_catalog.py가 이미 interests를 import함) 때문에
    이 모듈이 직접 못 지우므로, 호출부(main.py의 DELETE /interests/{id})가
    paper_catalog.delete_screenings_for_interest()와 같이 불러야 한다(08-04, 안 그러면
    고아 행이 남는 버그를 실사용 중 발견)."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute("DELETE FROM interests WHERE id = ?", (interest_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    # 수동 스모크 테스트 — 실제 data/app.db에 씀
    new_id = create_interest(
        title="양자컴퓨팅",
        looking_for="양자 오류 정정 최신 동향",
        already_known="큐비트·게이트 기본 개념",
        excluded_topics="양자 화학 시뮬레이션",
    )
    print(f"등록됨: id={new_id}")
    print(get_interest(new_id))
