# 연구 워크플로우 체크포인트 분기 기록 — research_sessions.py와 같은 경량 RDB
# 사이드테이블 패턴. LangGraph 체크포인터의 parent_config는 여기 못 쓴다: main.py의
# 복원 로직(advance_research, from_checkpoint_id 처리)이 aupdate_state를 항상 tip
# config(checkpoint_id 없음)에 쓰기 때문에, 새로 생기는 체크포인트의 parent는 항상
# "복원 직전 tip"이지 "값을 복사해온 과거 체크포인트"가 아니다 — 즉 체크포인트 체인
# 자체는 항상 선형이라 실제 분기 정보가 담기지 않는다(직접 재현해서 확인함, 08-04).
# 그래서 "이 턴이 어느 과거 체크포인트에서 갈라져 나왔는지"를 별도로 기록해야 브랜치형
# 타임라인의 세로선(계보) 연결을 그릴 수 있다.

import os
import sqlite3
from datetime import datetime, timezone

APP_DB_PATH = "data/app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_branches (
    child_checkpoint_id TEXT PRIMARY KEY,
    source_checkpoint_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    created_at TEXT NOT NULL
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


def record_branch(
    child_checkpoint_id: str,
    source_checkpoint_id: str,
    thread_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> None:
    """복원(from_checkpoint_id)으로 만들어진 턴의 결과 체크포인트(child)가 어느
    과거 체크포인트(source)에서 값을 복사해왔는지 기록한다. child_checkpoint_id는
    advance_research()가 ainvoke 이후 tip을 다시 조회해 얻은, 화면 히스토리에도
    그대로 찍히는 turn-final 체크포인트여야 한다(중간 노드 체크포인트가 아님)."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO research_branches "
            "(child_checkpoint_id, source_checkpoint_id, thread_id, created_at) VALUES (?, ?, ?, ?)",
            (child_checkpoint_id, source_checkpoint_id, thread_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def get_sources(
    child_checkpoint_ids: list[str], *, conn: sqlite3.Connection | None = None
) -> dict[str, str]:
    """child_checkpoint_id -> source_checkpoint_id 매핑. 여러 체크포인트를 한 번에
    조회(히스토리 화면이 한 번에 여러 행을 그리므로 N+1 쿼리를 피함)."""
    if not child_checkpoint_ids:
        return {}
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        placeholders = ",".join("?" * len(child_checkpoint_ids))
        rows = conn.execute(
            f"SELECT child_checkpoint_id, source_checkpoint_id FROM research_branches "
            f"WHERE child_checkpoint_id IN ({placeholders})",
            child_checkpoint_ids,
        ).fetchall()
        return {r["child_checkpoint_id"]: r["source_checkpoint_id"] for r in rows}
    finally:
        if owns_conn:
            conn.close()
