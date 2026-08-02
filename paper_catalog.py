# 논문 카탈로그 — RDB(SQLite). 논문 VDB(paper/paper_ingest.py)가 "내용 검색"을 맡고
# 여기는 "상태 관리"(등록 여부·추천/보유/기각·서지정보)만 맡는다. interests.py와 같은
# data/app.db를 다른 테이블로 공유(RoadMap "VDB vs RDB" 참고) — 경로 상수도 그쪽을 참조.
#
# 기본 키는 paper_id(normalize_paper_id: DOI>arXiv>해시, 한 번 정해지면 불변) — doi/
# arxiv_id는 nullable·unique 별도 컬럼으로 둬서, paper_id 하나로 못 잡는 매칭(추천
# 시점엔 arxiv_id만 알았는데 등록 시점엔 doi가 생기는 경우 등)을 보완할 여지를 남긴다.
# 실제 cross-id 매칭 로직은 아직 없음(단순 경로부터 — 필요해지면 이 컬럼으로 보완).
#
# 지표 필드(journal_ref, citation_count)는 계산 없이 컬럼만 미리 둔다 — 나중에 외부
# API 어댑터를 붙일 때 이 컬럼만 채우면 되게. status는 전용 함수(upsert_recommended/
# mark_owned/dismiss)로만 바꾼다 — 임의 필드 갱신 API는 안 둔다.

import os
import sqlite3
from datetime import datetime, timezone

import interests

APP_DB_PATH = interests.APP_DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    paper_id TEXT PRIMARY KEY,
    doi TEXT UNIQUE,
    arxiv_id TEXT UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    authors TEXT NOT NULL DEFAULT '',
    year TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'recommended' CHECK(status IN ('recommended', 'owned', 'dismissed')),
    journal_ref TEXT,
    citation_count INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def _get_connection() -> sqlite3.Connection:
    # interests._get_connection()을 재사용하지 않는다 — 그건 interests 스키마까지
    # 같이 적용해 책임이 섞인다. 경로 상수만 참조하고 스키마 적용은 각자 한다.
    os.makedirs(os.path.dirname(APP_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_paper(paper_id: str, *, conn: sqlite3.Connection | None = None) -> dict | None:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        row = conn.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
        return dict(row) if row else None
    finally:
        if owns_conn:
            conn.close()


def list_papers(*, status: str | None = None, conn: sqlite3.Connection | None = None) -> list[dict]:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        if status is None:
            rows = conn.execute("SELECT * FROM papers ORDER BY paper_id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM papers WHERE status = ? ORDER BY paper_id", (status,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


def upsert_recommended(
    paper_id: str,
    *,
    doi: str | None = None,
    arxiv_id: str | None = None,
    title: str = "",
    authors: str = "",
    year: str = "",
    conn: sqlite3.Connection | None = None,
) -> bool:
    """추천 검색(③)이 새 후보를 카탈로그에 기록한다. paper_id가 이미 있으면(추천이든
    보유든 기각이든) **손대지 않는다** — 특히 이미 owned/dismissed인 논문을 추천 검색이
    다시 찾아냈다고 recommended로 되돌리면 사용자가 이미 내린 결정(등록·기각)이 조용히
    뒤집힌다. 반환값은 "새로 추가됐는지" — 이미 있어서 스킵됐으면 False.
    """
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        if conn.execute("SELECT 1 FROM papers WHERE paper_id = ?", (paper_id,)).fetchone():
            return False
        now = _now()
        conn.execute(
            "INSERT INTO papers (paper_id, doi, arxiv_id, title, authors, year, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'recommended', ?, ?)",
            (paper_id, doi, arxiv_id, title, authors, year, now, now),
        )
        conn.commit()
        return True
    finally:
        if owns_conn:
            conn.close()


def mark_owned(
    paper_id: str,
    *,
    doi: str | None = None,
    arxiv_id: str | None = None,
    title: str = "",
    authors: str = "",
    year: str = "",
    conn: sqlite3.Connection | None = None,
) -> None:
    """paper_id를 owned로 표시한다 — 있으면 status만 바꾸고, 없으면 새로 만든다.
    register_paper()가 등록 성공 시 호출한다."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        now = _now()
        if conn.execute("SELECT 1 FROM papers WHERE paper_id = ?", (paper_id,)).fetchone():
            conn.execute(
                "UPDATE papers SET status = 'owned', updated_at = ? WHERE paper_id = ?",
                (now, paper_id),
            )
        else:
            conn.execute(
                "INSERT INTO papers (paper_id, doi, arxiv_id, title, authors, year, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'owned', ?, ?)",
                (paper_id, doi, arxiv_id, title, authors, year, now, now),
            )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def dismiss(paper_id: str, *, conn: sqlite3.Connection | None = None) -> bool:
    """추천을 기각한다 — 기각 이력은 그 자체로 스크리닝 기준의 정답 레이블이 된다
    (RoadMap "기각 이력이 평가 기준의 정답 레이블" 참고). 존재하지 않는 paper_id면 False."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute(
            "UPDATE papers SET status = 'dismissed', updated_at = ? WHERE paper_id = ?",
            (_now(), paper_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    # 수동 스모크 테스트 — 실제 data/app.db에 씀
    added = upsert_recommended("arxiv:2401.12345", arxiv_id="2401.12345", title="테스트 논문")
    print(f"추천 등록: {added}, 현재: {get_paper('arxiv:2401.12345')}")
    mark_owned("arxiv:2401.12345")
    print(f"보유 전환 후: {get_paper('arxiv:2401.12345')}")
