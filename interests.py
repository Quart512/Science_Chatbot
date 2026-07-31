# =========================================================
# 관심사 저장소(①) — RDB(SQLite). RoadMap "VDB vs RDB" 설계 노트 참고: 필드 단위 수정이
# 흔하고(문서 작성기의 "기존 편집 제안") 논문 카탈로그와 다대다 조인이 필요해서(관심사
# 카드별 보유·추천·권위 논문 목록) VDB가 아니라 RDB로 결정됐다.
#
# data/app.db에 저장한다 — orchestrator.py의 CHECKPOINT_DB_PATH(체크포인트)와 파일을
# 분리하되(전자는 LangGraph가 스키마 관리, 이건 우리 스키마) 같은 data/ 디렉터리를 쓴다
# (chroma_db/와 같은 패턴, RoadMap "파일 배치" 참고). 실험도구(⑤)·논문 카탈로그도 결국
# RDB로 이 파일에 합류할 예정이라 도메인마다 DB 파일을 쪼개지 않는다 — 관심사↔논문
# 카탈로그처럼 조인이 필요한 관계가 이미 예정돼 있는데, SQLite는 파일이 다르면 조인이
# 번거로워진다(ATTACH 필요). 테이블 하나뿐인 지금은 SQLAlchemy 같은 ORM 없이 표준
# 라이브러리 sqlite3로 충분하다(단순 경로부터) — 나중에 조인·마이그레이션이 복잡해지면
# 재검토.
#
# 테스트 방식: Chroma를 흉내낸 FakeVectorstore 같은 가짜가 필요 없다 — sqlite3는
# ":memory:"로 열면 진짜 DB가 밀리초 단위로 돈다(tests/test_interests.py 참고).
# =========================================================

import os
import sqlite3
from datetime import datetime, timezone

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
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """테이블이 없으면 만든다(CREATE TABLE IF NOT EXISTS라 여러 번 불러도 안전) — 정식
    마이그레이션 도구는 테이블이 하나뿐인 지금은 과하다(단순 경로부터). conn을 인자로
    받는 이유: 실제 연결(_get_connection())과 테스트용 :memory: 연결 양쪽에 같은 스키마를
    적용해야 하는데, 후자는 _get_connection()을 거치지 않으므로 명시적으로 호출해야 한다."""
    conn.executescript(SCHEMA)
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
    """관심사 하나를 등록하고 새 id를 반환한다. conn을 안 넘기면 이 함수가 알아서
    열고 닫는다(paper_ingest.py의 vectorstore=None 패턴과 같은 결 — 호출자가 커넥션을
    공유하고 싶을 때만 명시적으로 넘기면 됨)."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        now = _now()
        cur = conn.execute(
            "INSERT INTO interests (title, looking_for, already_known, excluded_topics, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, looking_for, already_known, excluded_topics, now, now),
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
        rows = conn.execute("SELECT * FROM interests ORDER BY id").fetchall()
        return [dict(r) for r in rows]
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
    """주어진 필드만 부분 갱신한다(문서 작성기의 "기존 편집 제안"이 필드 단위로 고치는
    용도 — VDB였다면 문서 전체를 재구성해야 했을 일). 반환값은 실제로 갱신된 행이
    있었는지(id가 존재했는지) — 없는 id를 조용히 무시하지 않고 호출자가 알 수 있게 한다.

    _UPDATABLE_FIELDS 밖의 키가 오면 ValueError — 오타(예: "titel")를 조용히 무시하는
    대신 바로 드러낸다. 필드명이 SQL 문자열에 그대로 들어가므로(값은 파라미터 바인딩,
    컬럼명은 f-string) 이 화이트리스트 검사가 인젝션 방지 역할도 겸한다.
    """
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
