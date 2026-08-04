# 연구 워크플로우 — 단계별 메모(스냅샷에 필기) — research_branches.py와 같은 경량
# RDB 사이드테이블 패턴. WorkflowState에 notes 필드를 두는 대안(A)도 검토했으나
# aupdate_state는 항상 tip에만 쓰여서(research_branches.py 주석 참고) 과거 체크포인트
# 자체에는 못 남는다 — "스냅샷에 필기를 남기고 수정"이라는 요구를 문자 그대로
# 만족하려면 체크포인트를 안 건드리는 별도 저장소가 필요하다(RoadMap "타임라인·체크
# 결합(브랜치형)" 설계 노트, 08-04 사용자 결정).
#
# 빈 문자열 저장은 "메모 지움"으로 취급해 행을 삭제한다 — 노트 하나 = 행 하나라
# equipment.py의 필드별 "빈 문자열=명시적으로 지움"과 달리 여기선 빈 문자열 행을
# 남겨둘 이유가 없다(행 존재 자체가 "메모 있음"과 동치인 게 더 단순하다).

import os
import sqlite3
from datetime import datetime, timezone

APP_DB_PATH = "data/app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_notes (
    checkpoint_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    note TEXT NOT NULL,
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


def set_note(
    checkpoint_id: str, thread_id: str, note: str, *, conn: sqlite3.Connection | None = None
) -> None:
    """checkpoint_id의 메모를 저장한다. note가 빈 문자열(공백만도 포함)이면 행을
    지운다 — "메모 없음" 상태를 별도로 구분할 필요 없이 행이 없으면 곧 메모가 없는 것."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        if not note.strip():
            conn.execute("DELETE FROM research_notes WHERE checkpoint_id = ?", (checkpoint_id,))
        else:
            conn.execute(
                "INSERT OR REPLACE INTO research_notes (checkpoint_id, thread_id, note, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (checkpoint_id, thread_id, note, datetime.now(timezone.utc).isoformat()),
            )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def get_notes_for_checkpoints(
    checkpoint_ids: list[str], *, conn: sqlite3.Connection | None = None
) -> dict[str, str]:
    """checkpoint_id -> note 매핑. 여러 체크포인트를 한 번에 조회(히스토리 화면이
    한 번에 여러 행을 그리므로 N+1 쿼리를 피함 — research_branches.get_sources와
    같은 이유)."""
    if not checkpoint_ids:
        return {}
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        placeholders = ",".join("?" * len(checkpoint_ids))
        rows = conn.execute(
            f"SELECT checkpoint_id, note FROM research_notes WHERE checkpoint_id IN ({placeholders})",
            checkpoint_ids,
        ).fetchall()
        return {r["checkpoint_id"]: r["note"] for r in rows}
    finally:
        if owns_conn:
            conn.close()
