# 연구 세션(⑥) 목록 — 챗 세션과 같은 패턴(사이드바 목록 + 제목 수정 + 닫기)으로
# research_workflow.py의 thread_id를 관리한다. interests.py와 완전히 같은 CRUD
# 패턴이라 구조를 그대로 베꼈다 — 차이는 PK가 자동증가 id가 아니라 thread_id라는
# 점(research_workflow.graph를 그 thread_id로 ainvoke하는 것과 짝이 맞아야 하므로
# 호출자가 uuid4()로 미리 발급해 넘긴다). 스키마·설계 근거는
# docs/RoadMap.md "연구 워크플로우 화면 — 확정된 설계 §4" 참고.

import os
import sqlite3
from datetime import datetime, timezone

APP_DB_PATH = "data/app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_sessions (
    thread_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    topic TEXT NOT NULL,
    stage TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """테이블이 없으면 만든다. conn을 인자로 받는 이유는 interests.py와 같다 —
    실제 연결(_get_connection())과 테스트용 :memory: 연결 양쪽에 적용해야 한다."""
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


def create_session(
    thread_id: str,
    title: str,
    topic: str,
    stage: str = "hypothesis",
    *,
    conn: sqlite3.Connection | None = None,
) -> None:
    """새 연구 세션을 등록한다. thread_id는 새 id를 반환하는 create_interest()와
    달리 호출자가 미리 정해 넘긴다 — 같은 thread_id로 research_workflow.graph를
    ainvoke하는 게 이 함수 호출과 짝을 이뤄야 하기 때문."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        now = _now()
        conn.execute(
            "INSERT INTO research_sessions (thread_id, title, topic, stage, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (thread_id, title, topic, stage, now, now),
        )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def list_sessions(*, conn: sqlite3.Connection | None = None) -> list[dict]:
    """생성 순서대로 반환 — thread_id가 uuid라 id처럼 정렬이 곧 생성순이 아니므로
    created_at으로 정렬한다(interests.list_interests()는 ORDER BY id)."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        rows = conn.execute("SELECT * FROM research_sessions ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


def get_session(thread_id: str, *, conn: sqlite3.Connection | None = None) -> dict | None:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM research_sessions WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        if owns_conn:
            conn.close()


def update_title(thread_id: str, title: str, *, conn: sqlite3.Connection | None = None) -> bool:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute(
            "UPDATE research_sessions SET title = ?, updated_at = ? WHERE thread_id = ?",
            (title, _now(), thread_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


def update_stage(thread_id: str, stage: str, *, conn: sqlite3.Connection | None = None) -> bool:
    """목록에 보여줄 현재 단계만 갱신한다 — 실제 워크플로우 상태(체크포인트)와는
    별개 채널이라 자동 동기화가 없다. 단계를 트리거하는 쪽(main.py 엔드포인트)이
    ainvoke 성공 후 직접 불러줘야 한다."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute(
            "UPDATE research_sessions SET stage = ?, updated_at = ? WHERE thread_id = ?",
            (stage, _now(), thread_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


def delete_session(thread_id: str, *, conn: sqlite3.Connection | None = None) -> bool:
    """세션 목록에서만 지운다 — 실제 LangGraph 체크포인트(research_workflow_checkpoints.sqlite)는
    안 지운다(RoadMap §4: 내부 스키마라 직접 삭제가 까다롭고 개인 용도라 용량 문제도 없음)."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute("DELETE FROM research_sessions WHERE thread_id = ?", (thread_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    # 수동 스모크 테스트 — 실제 data/app.db에 씀
    import uuid

    tid = str(uuid.uuid4())
    create_session(tid, title="테스트 연구", topic="양자컴퓨팅 오류 정정")
    print(f"등록됨: thread_id={tid}")
    print(get_session(tid))
