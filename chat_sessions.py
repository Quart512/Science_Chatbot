# 챗(④) 세션 목록 — research_sessions.py와 완전히 같은 패턴(사이드바 목록 + 제목 수정 +
# 닫기)이다. 차이는 stage/topic이 없다는 것뿐 — 챗은 연구처럼 미리 정해지는 주제·단계가
# 없고, 첫 메시지를 보낸 시점에 그 프롬프트 앞부분을 title로 삼아 lazy 생성한다
# (main.py의 /query 핸들러가 호출). 스키마·설계 근거는 docs/RoadMap.md "프론트 개선
# 백로그 (08-05)" ⑤ 참고.

import os
import sqlite3
from datetime import datetime, timezone

APP_DB_PATH = "data/app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    thread_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """테이블이 없으면 만든다. conn을 인자로 받는 이유는 research_sessions.py와 같다 —
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
    *,
    conn: sqlite3.Connection | None = None,
) -> None:
    """새 챗 세션을 등록한다. thread_id는 호출자(main.py /query 핸들러)가 이미 정해
    넘긴다 — 같은 thread_id로 orchestrator.graph를 astream하는 것과 짝을 이뤄야 한다."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        now = _now()
        conn.execute(
            "INSERT INTO chat_sessions (thread_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (thread_id, title, now, now),
        )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def list_sessions(*, conn: sqlite3.Connection | None = None) -> list[dict]:
    """최근 사용 순으로 반환 — 오른쪽 상시 패널이 "가장 최근 세션"을 이어서 열 때
    이 순서를 그대로 쓴다(list_sessions()[0]). research_sessions.list_sessions()는
    생성순(created_at)이라 다르다 — 거긴 목록 훑어보기 용도라 순서가 안 바뀌는 쪽이
    낫고, 여긴 "마지막으로 쓴 대화가 위로" 쪽이 자연스럽다."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        rows = conn.execute("SELECT * FROM chat_sessions ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


def get_session(thread_id: str, *, conn: sqlite3.Connection | None = None) -> dict | None:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM chat_sessions WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        if owns_conn:
            conn.close()


def touch_session(thread_id: str, *, conn: sqlite3.Connection | None = None) -> bool:
    """updated_at만 지금 시각으로 갱신 — /query가 매 턴마다 불러서 list_sessions()의
    "최근 순" 정렬이 실제 사용 시점을 반영하게 한다."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE thread_id = ?", (_now(), thread_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


def update_title(thread_id: str, title: str, *, conn: sqlite3.Connection | None = None) -> bool:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute(
            "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE thread_id = ?",
            (title, _now(), thread_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


def delete_session(thread_id: str, *, conn: sqlite3.Connection | None = None) -> bool:
    """세션 목록에서만 지운다 — 실제 LangGraph 체크포인트(checkpoints.sqlite)는 안 지운다
    (research_sessions.delete_session()과 같은 이유: 내부 스키마라 직접 삭제가 까다롭고
    개인 용도라 용량 문제도 없음)."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute("DELETE FROM chat_sessions WHERE thread_id = ?", (thread_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    # 수동 스모크 테스트 — 실제 data/app.db에 씀
    import uuid

    tid = str(uuid.uuid4())
    create_session(tid, title="테스트 대화")
    print(f"등록됨: thread_id={tid}")
    print(get_session(tid))
