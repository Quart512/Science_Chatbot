# 사용자 API 키 저장소(08-05, 설치판 설정 화면) — interests.py와 완전히 같은 패턴
# (순수 sqlite3, data/app.db를 다른 테이블로 공유, ORM 없음). RoadMap "싱글 유저 로컬
# 앱 확정" 결정("API 키는 사용자 본인 입력")의 저장 부분 — 여기 저장된 값이 models.py의
# invoke_with_fallback()에서 .env(환경변수) 값보다 우선 적용된다(DB 우선, .env 폴백).
#
# 지원 provider는 화면에서 입력받는 두 개(gemini/claude)뿐이다 — Qwen-tuned는 로컬
# llama-server라 애초에 키가 필요 없다(models.py의 더미 "not-needed" 참고).

import os
import sqlite3
from datetime import datetime, timezone

APP_DB_PATH = "data/app.db"

SUPPORTED_PROVIDERS = ("gemini", "claude")

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    provider TEXT PRIMARY KEY,
    api_key TEXT NOT NULL,
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_provider(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"지원하지 않는 provider: {provider!r} (지원: {SUPPORTED_PROVIDERS})")


def get_api_key(provider: str, *, conn: sqlite3.Connection | None = None) -> str | None:
    """저장된 키가 없으면 None — 호출부(models.py)가 .env 폴백 여부를 판단할 수 있게
    "빈 문자열"이 아니라 명확히 None을 돌려준다."""
    _check_provider(provider)
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        row = conn.execute("SELECT api_key FROM api_keys WHERE provider = ?", (provider,)).fetchone()
        return row["api_key"] if row else None
    finally:
        if owns_conn:
            conn.close()


def set_api_key(provider: str, api_key: str, *, conn: sqlite3.Connection | None = None) -> None:
    """upsert — 빈 문자열을 저장하면 안 됨(get_api_key가 "없음"과 구분 못 함), 삭제는
    delete_api_key()로 명시적으로."""
    _check_provider(provider)
    if not api_key:
        raise ValueError("api_key는 빈 문자열일 수 없습니다 — 삭제하려면 delete_api_key()를 쓰세요")
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        conn.execute(
            "INSERT INTO api_keys (provider, api_key, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(provider) DO UPDATE SET api_key = excluded.api_key, updated_at = excluded.updated_at",
            (provider, api_key, _now()),
        )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def delete_api_key(provider: str, *, conn: sqlite3.Connection | None = None) -> bool:
    """저장된 키를 지운다(다음 호출부터 .env 폴백으로 돌아감). 반환값은 실제로 지워진
    행이 있었는지."""
    _check_provider(provider)
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute("DELETE FROM api_keys WHERE provider = ?", (provider,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


def _mask(api_key: str) -> str:
    """끝 4자리만 남기고 마스킹 — 화면·API 응답에 평문 키를 다시 안 돌려주기 위함
    (08-05 설계: 조회는 마스킹된 상태만, 새 값은 POST로만 받음)."""
    if len(api_key) <= 4:
        return "*" * len(api_key)
    return "*" * (len(api_key) - 4) + api_key[-4:]


def list_key_status(*, conn: sqlite3.Connection | None = None) -> list[dict]:
    """화면에 뿌릴 상태 목록 — SUPPORTED_PROVIDERS 전부에 대해 저장 여부·마스킹된
    끝자리·갱신 시각을 돌려준다(저장 안 된 provider도 "saved": False로 포함해 프론트가
    항상 같은 모양의 목록을 그릴 수 있게)."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        rows = {r["provider"]: r for r in conn.execute("SELECT * FROM api_keys").fetchall()}
        return [
            {
                "provider": provider,
                "saved": provider in rows,
                "masked_key": _mask(rows[provider]["api_key"]) if provider in rows else None,
                "updated_at": rows[provider]["updated_at"] if provider in rows else None,
            }
            for provider in SUPPORTED_PROVIDERS
        ]
    finally:
        if owns_conn:
            conn.close()
