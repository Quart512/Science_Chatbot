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
#
# interest_paper(08-03 추가) — 관심사↔논문 다대다 조인. papers 테이블(전역 상태)만
# 있으면 "이 관심사에 추천된 논문"을 못 구한다 — 한 논문이 여러 관심사와 관련될 수
# 있어 어느 한쪽에 태그를 붙이는 방식(예: papers에 interest_id 컬럼)은 안 맞는다.
# ③ 추천 검색(paper_recommend.py)이 스크리닝한 후보마다(관련 있음/없음 둘 다) 여기
# 기록한다 — 반환 목록이 이미 둘 다 포함하는 것과 같은 이유("추천에서 끝나고 결정은
# 사람이"). is_relevant/reasoning은 자동 계산된 신호일 뿐 사용자 결정이 아니므로
# upsert_recommended와 달리 재스크리닝 시 최신 값으로 덮어쓴다(record_screening 참고).

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
    filename TEXT NOT NULL DEFAULT '',
    file_path TEXT,
    content_sha256 TEXT,
    analysis_status TEXT NOT NULL DEFAULT 'untracked',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interest_paper (
    interest_id INTEGER NOT NULL,
    paper_id TEXT NOT NULL,
    is_relevant INTEGER NOT NULL,
    reasoning TEXT NOT NULL DEFAULT '',
    screened_at TEXT NOT NULL,
    PRIMARY KEY (interest_id, paper_id)
);
"""

# CREATE TABLE IF NOT EXISTS는 테이블이 이미 있으면 새로 추가한 컬럼(filename)을 기존
# DB에 안 만든다 — equipment.py가 precautions 컬럼에서 실제로 겪은 문제(§7.4 참고)와
# 같은 패턴이라 같은 방식으로 막는다. 배포 환경(EC2 바인드 마운트)의 기존 papers
# 테이블에 이 코드를 올리면 filename 없이 INSERT하다 "no such column"으로 터진다.
#
# file_path/content_sha256/analysis_status(08-05, "논문 파일 경로 추적 재설계" 착수
# ①) — RoadMap 설계 노트 참고. file_path는 library/ 루트 기준 **상대경로**로 둔다(절대
# 경로면 컨테이너 마운트 지점이 바뀌거나 portable 번들로 옮겨질 때 깨진다 — 설계 노트
# 항목 A). content_sha256은 DOI/arXiv 논문의 paper_id가 해시가 아니라(normalize_paper_id:
# DOI>arXiv>해시 우선순위) 그 경우도 파일↔레코드를 매칭할 별도 컬럼이 필요해서 둔다
# (설계 노트 항목 C — "경로는 변할 수 있는 속성, 해시가 신원"). analysis_status는 등록
# (트래킹)과 분석(파싱·색인)을 분리하는 다음 단계(설계 노트 항목 G)를 위해 미리 컬럼만
# 마련 — 지금은 아무 코드도 이 값을 안 채운다.
_EXPECTED_COLUMNS = {
    "filename": "TEXT NOT NULL DEFAULT ''",
    "file_path": "TEXT",
    "content_sha256": "TEXT",
    "analysis_status": "TEXT NOT NULL DEFAULT 'untracked'",
}


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(papers)")}
    for name, ddl in _EXPECTED_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE papers ADD COLUMN {name} {ddl}")
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

    filename이 없는 이유: 추천 후보는 검색 결과(arxiv 등)에서 오므로 업로드 파일 자체가
    없다 — 빈 문자열로 남고, 실제 파일명은 사용자가 나중에 등록(mark_owned)할 때 채워진다.
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
    filename: str = "",
    conn: sqlite3.Connection | None = None,
) -> None:
    """paper_id를 owned로 표시한다 — 있으면 status만 바꾸고, 없으면 새로 만든다.
    register_paper()가 등록 성공 시 호출한다. filename(업로드 원본 파일명)은 title이
    비어있는 논문(서지정보를 못 찾은 경우)을 화면에서 해시 대신 사람이 읽을 수 있는
    이름으로 보여주는 차선책 — 08-04 사용자 요청("해쉬값은 최후순위, 파일명이 그 앞")."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        now = _now()
        if conn.execute("SELECT 1 FROM papers WHERE paper_id = ?", (paper_id,)).fetchone():
            conn.execute(
                "UPDATE papers SET status = 'owned', filename = ?, updated_at = ? WHERE paper_id = ?",
                (filename, now, paper_id),
            )
        else:
            conn.execute(
                "INSERT INTO papers (paper_id, doi, arxiv_id, title, authors, year, status, filename, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'owned', ?, ?, ?)",
                (paper_id, doi, arxiv_id, title, authors, year, filename, now, now),
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


def record_screening(
    interest_id: int, paper_id: str, *, is_relevant: bool, reasoning: str = "",
    conn: sqlite3.Connection | None = None,
) -> None:
    """관심사 하나가 논문 하나를 스크리닝한 결과를 기록한다(③ 추천 검색이 후보마다
    호출, 관련 있음/없음 둘 다) — 파일 상단 주석 참고. 같은 (interest_id, paper_id)
    쌍이 다시 채점되면(refresh_for_interest의 재스크리닝) 최신 판정으로 덮어쓴다."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        now = _now()
        if conn.execute(
            "SELECT 1 FROM interest_paper WHERE interest_id = ? AND paper_id = ?",
            (interest_id, paper_id),
        ).fetchone():
            conn.execute(
                "UPDATE interest_paper SET is_relevant = ?, reasoning = ?, screened_at = ? "
                "WHERE interest_id = ? AND paper_id = ?",
                (is_relevant, reasoning, now, interest_id, paper_id),
            )
        else:
            conn.execute(
                "INSERT INTO interest_paper (interest_id, paper_id, is_relevant, reasoning, screened_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (interest_id, paper_id, is_relevant, reasoning, now),
            )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def list_papers_for_interest(
    interest_id: int, *, only_relevant: bool = False, conn: sqlite3.Connection | None = None,
) -> list[dict]:
    """이 관심사에 스크리닝된 논문을 papers와 조인해 반환 — 서지정보(title 등)와 전역
    status(recommended/owned/dismissed)까지 함께 나온다. only_relevant=True면 관련
    있다고 판정된 것만(라이브러리 카드가 기본으로 보여줄 목록), 기본은 둘 다.

    LEFT JOIN을 쓴다 — 카탈로그(papers)는 "관련 있는 것만" 기록하는 게 기존 원칙
    (recommend_for_interest 참고)이라, 관련 없다고 판정된 논문은 papers에 행이 없다.
    INNER JOIN이면 그런 행이 통째로 사라져 "관련 없음도 기록한다"는 이 테이블의
    목적 자체가 조회에서 무효화된다. papers 쪽 필드는 없으면 전부 None으로 나온다."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        query = (
            "SELECT interest_paper.paper_id, papers.doi, papers.arxiv_id, papers.title, papers.authors, "
            "papers.year, papers.status, papers.journal_ref, papers.citation_count, "
            "interest_paper.is_relevant, interest_paper.reasoning, interest_paper.screened_at "
            "FROM interest_paper LEFT JOIN papers ON papers.paper_id = interest_paper.paper_id "
            "WHERE interest_paper.interest_id = ?"
        )
        params = [interest_id]
        if only_relevant:
            query += " AND interest_paper.is_relevant = 1"
        query += " ORDER BY interest_paper.is_relevant DESC, interest_paper.screened_at DESC"
        rows = conn.execute(query, params).fetchall()
        # sqlite3는 is_relevant를 0/1 정수로 돌려준다 — record_screening()이 bool을
        # 받는 것과 대칭으로 여기서 다시 bool로 되돌려 호출자가 int/bool을 안 헷갈리게 한다.
        return [{**dict(r), "is_relevant": bool(r["is_relevant"])} for r in rows]
    finally:
        if owns_conn:
            conn.close()


def delete_screenings_for_interest(interest_id: int, *, conn: sqlite3.Connection | None = None) -> None:
    """관심사 하나가 남긴 interest_paper 행을 전부 지운다 — 관심사를 삭제할 때
    interests.delete_interest()와 같이 불러야 한다(08-04 실사용 중 발견한 버그: 이걸
    안 부르면 지운 관심사가 남긴 스크리닝 기록이 고아로 남아 "관심사와 무관한데
    recommended"로 혼란을 준다). interest_paper는 이 모듈이 스키마를 소유하므로
    interests.py가 직접 지우지 않고 여기 함수를 통해서만 지운다(순환 import 방지 +
    각 모듈이 자기 테이블만 아는 원칙)."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        conn.execute("DELETE FROM interest_paper WHERE interest_id = ?", (interest_id,))
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    # 수동 스모크 테스트 — 실제 data/app.db에 씀
    added = upsert_recommended("arxiv:2401.12345", arxiv_id="2401.12345", title="테스트 논문")
    print(f"추천 등록: {added}, 현재: {get_paper('arxiv:2401.12345')}")
    mark_owned("arxiv:2401.12345")
    print(f"보유 전환 후: {get_paper('arxiv:2401.12345')}")
    record_screening(1, "arxiv:2401.12345", is_relevant=True, reasoning="테스트 근거")
    print(f"관심사 1의 논문 목록: {list_papers_for_interest(1)}")
