# 지식 노트 — 사용자가 직접 쓰는 노트·정리 문서. RAG 검색 대상이지만 편집이 일급
# 연산이라(관심사를 VDB에서 RDB로 옮긴 것과 같은 이유, RoadMap 07-28 "편집이 일급
# 연산이다" 참고) 진짜 텍스트는 여기(SQLite, data/app.db — interests.py/equipment.py와
# 같은 파일을 다른 테이블로 공유)에 두고, VDB(retrieval.notes_vectorstore)는 검색용
# 청크만 담는 disposable 인덱스로 쓴다. 노트가 만들어지거나 본문이 바뀔 때마다 그
# 노트 몫 청크를 통째로 지우고 다시 만든다 — 부분 재인코딩은 안 한다(paper_ingest.
# register_paper()의 재등록 처리와 같은 이유: 편집 한 번에 청크 경계가 전부 밀리므로
# "바뀐 청크만"이라는 개념이 애초에 안정적이지 않다).
#
# doc_type이 아니라 source_type: "user_note" 태그를 쓴다(paper_ingest의 fulltext_chunk/
# summary/abstract 구분과 다른 축) — 물리 QA의 retrieve()/verify()가 이 태그로 노트를
# 논문·코퍼스보다 낮은 신뢰도로 취급하게 될 예정(RoadMap 참고, 아직 미연동).

import os
import sqlite3
from datetime import datetime, timezone

from langchain_text_splitters import RecursiveCharacterTextSplitter

import interests

APP_DB_PATH = interests.APP_DB_PATH

_UPDATABLE_FIELDS = ("title", "text")

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# ingest.py(파인만 강의록)와 같은 설정 — 노트도 학술논문 구조(헤더·References 등)가
# 없는 평범한 텍스트라 paper_chunking.py의 헤더 기반 분할이 아니라 이 단순 분할이 맞다.
_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)


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


def _get_notes_vectorstore():
    # 함수 안에서 import — 무거운 임베딩 모델 로딩을 실제 호출 시점까지 미룬다
    # (paper_ingest.py의 _get_papers_vectorstore()와 같은 이유).
    from retrieval import notes_vectorstore
    return notes_vectorstore


def _reindex(note_id: int, text: str, *, vectorstore=None) -> None:
    """이 노트의 검색용 청크를 통째로 지우고(있었다면) 다시 만든다. 텍스트가 비어
    있으면 지우기만 하고 끝(청크 없음 — 빈 문자열을 쪼개봤자 의미 없음)."""
    vectorstore = vectorstore or _get_notes_vectorstore()
    vectorstore.delete(where={"note_id": note_id})
    if not text:
        return
    chunks = _SPLITTER.split_text(text)
    if not chunks:
        return
    vectorstore.add_texts(
        texts=chunks,
        ids=[f"note-{note_id}-{i}" for i in range(len(chunks))],
        metadatas=[{"note_id": note_id, "source_type": "user_note"} for _ in chunks],
    )


def create_note(
    title: str = "", text: str = "", *, conn: sqlite3.Connection | None = None, vectorstore=None,
) -> int:
    """노트 하나를 등록하고 새 id를 반환한다. SQLite에 본문을 쓰고 VDB에 검색용
    청크를 만든다(순서상 SQLite 먼저 — id가 청크 메타데이터에 필요)."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        now = _now()
        cur = conn.execute(
            "INSERT INTO notes (title, text, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title, text, now, now),
        )
        conn.commit()
        note_id = cur.lastrowid
        _reindex(note_id, text, vectorstore=vectorstore)
        return note_id
    finally:
        if owns_conn:
            conn.close()


def get_note(note_id: int, *, conn: sqlite3.Connection | None = None) -> dict | None:
    """SQLite에서 그대로 읽는다 — 청크 재조합이 필요 없다(그게 이 설계의 핵심)."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return dict(row) if row else None
    finally:
        if owns_conn:
            conn.close()


def list_notes(*, conn: sqlite3.Connection | None = None) -> list[dict]:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        rows = conn.execute("SELECT * FROM notes ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


def update_note(
    note_id: int, *, conn: sqlite3.Connection | None = None, vectorstore=None, **fields,
) -> bool:
    """주어진 필드만 부분 갱신한다(equipment.update_equipment와 같은 계약) — 반환값은
    실제로 갱신된 행이 있었는지. text가 바뀔 때만 VDB를 재색인한다(title만 바뀌면
    검색 청크는 그대로 유효하므로 건드릴 이유가 없다)."""
    unknown = set(fields) - set(_UPDATABLE_FIELDS)
    if unknown:
        raise ValueError(f"업데이트할 수 없는 필드: {unknown}")
    if not fields:
        return False

    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        set_clause = ", ".join(f"{k} = ?" for k in fields) + ", updated_at = ?"
        values = [*fields.values(), _now(), note_id]
        cur = conn.execute(f"UPDATE notes SET {set_clause} WHERE id = ?", values)
        conn.commit()
        updated = cur.rowcount > 0
        if updated and "text" in fields:
            _reindex(note_id, fields["text"], vectorstore=vectorstore)
        return updated
    finally:
        if owns_conn:
            conn.close()


def delete_note(note_id: int, *, conn: sqlite3.Connection | None = None, vectorstore=None) -> bool:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        if deleted:
            (vectorstore or _get_notes_vectorstore()).delete(where={"note_id": note_id})
        return deleted
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    # 수동 스모크 테스트 — 실제 data/app.db + chroma_db에 씀
    new_id = create_note("파인만 8장 요점", "확률론적 해석의 핵심은...")
    print(f"등록됨: id={new_id}")
    print(get_note(new_id))
    update_note(new_id, text="확률론적 해석의 핵심은... (수정됨)")
    print(f"수정 후: {get_note(new_id)}")
