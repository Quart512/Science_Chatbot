# =========================================================
# 논문 카탈로그 — RDB(SQLite). 논문 VDB(paper/paper_ingest.py)는 "내용 검색용"이고 이건
# "상태 관리용"이라 역할이 분리된다(RoadMap "데이터 서비스" 표 참고) — 전문 검색은 VDB가
# 계속 담당하고, 여기서는 등록 여부·추천/보유/기각 상태·서지정보만 관리한다.
#
# interests.py와 같은 data/app.db에 다른 테이블로 둔다(RDB 파일은 도메인별로 안 쪼갬 —
# RoadMap "VDB vs RDB" 설계 노트 참고). APP_DB_PATH는 여기서 새로 정의하지 않고
# interests.py 걸 그대로 참조 — 두 모듈이 같은 파일을 가리켜야 하는데 상수를 복제하면
# 하나만 고치고 잊어버릴 위험이 있다.
#
# 기본 키는 paper_id(paper/paper_id.py의 normalize_paper_id() — DOI > arXiv > 파일 해시
# 우선순위)다. **한 번 정해지면 불변**이다 — 나중에 preprint가 게재돼 DOI가 생겨도 paper_id는
# 그대로 두고 doi 컬럼만 채운다(RoadMap "논문 id 정규화 + 재등록 처리" 설계 노트 참고) —
# 그래야 이 논문을 가리키는 다른 참조(VDB 청크 id 등)가 고아가 안 된다. doi/arxiv_id를
# 별도 nullable·unique 컬럼으로 두는 이유도 같다 — 추천 시점엔 arxiv_id만 있었는데 등록
# 시점엔 doi가 생기는 경우처럼, paper_id 하나로 못 잡는 매칭을 이 컬럼들로 보완할 수 있게
# (실제 매칭 로직은 register_paper() 연동 단계에서 다룰 것 — 아직 미구현).
#
# 지표 필드(journal_ref, citation_count)는 값을 계산하지 않고 컬럼만 미리 둔다 — arxiv만
# 쓰는 지금은 항상 비어 있고, 나중에 OpenAlex 등 API 어댑터를 붙일 때 이 컬럼만 채우면
# 코드 변경이 필요 없다(RoadMap "외부 API는 최종 단계의 어댑터" 참고).
#
# status는 자유 문자열 갱신이 아니라 전용 함수(upsert_recommended/mark_owned/dismiss)로만
# 바꾼다 — 상태 전이가 의미 있는 이벤트라(추천→보유, 추천→기각 등) interests.py의
# update_interest()처럼 아무 필드나 자유롭게 고치는 API를 주지 않는다.
#
# 테스트 방식: interests.py와 동일 — sqlite3 ":memory:" 연결을 그대로 쓴다(가짜 객체 불필요).
# =========================================================

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
    # interests._get_connection()을 그대로 재사용하지 않는다 — 그 함수는 interests
    # 테이블 스키마도 같이 적용하는데, papers 연결을 열 때마다 interests 쪽 마이그레이션이
    # 딸려 오는 건 두 테이블의 책임이 뒤섞이는 것이라 각자 자기 스키마만 챙긴다(경로
    # 상수만 interests.APP_DB_PATH를 그대로 참조해 파일이 갈라지는 걸 막는다).
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
    """paper_id를 owned로 표시한다 — 이미 카탈로그에 있으면(추천이었든 아니든) status만
    owned로 바꾸고, 없으면(추천된 적 없이 바로 등록된 논문) 새로 만든다. register_paper()
    연동(추후 단계)이 등록 시점에 호출할 지점 — 아직은 이 함수만 준비해두고 실제 연동은
    안 함."""
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
