# 지인 테스트용 사용 데이터 공유(08-09) — 로드맵 "텔레메트리 + 동의" 항목(08-05에
# "무기한 연기, 후순위"로 미뤄뒀던 것)을 사용자 요청으로 다시 꺼내 구현한다. api_keys.py와
# 완전히 같은 패턴(순수 sqlite3, data/app.db를 다른 테이블로 공유, ORM 없음).
#
# 설계: 자체 수집 파이프라인을 새로 안 만들고 LangSmith(LangChain 팀이 이미 만들어둔
# 추적 서비스)에 얹는다 — 이미 이 프로젝트가 LangGraph로 돌아가서 트레이싱 자체는
# 라이브러리가 공짜로 해준다. 저자 본인 계정과 "지인 테스트" 트레이스가 섞이면 안 되니
# 프로젝트를 분리하고(LANGSMITH_PROJECT), 실명 대신 설치 하나당 한 번 발급되는 익명
# install_id를 태그로 붙여 "누가"가 아니라 "이 설치가 무엇을 얼마나" 정도만 구분한다.
#
# 저자의 LangSmith API 키는 소스에 절대 안 박는다(이 저장소는 퍼블릭이다) — release.yml이
# GitHub Actions 시크릿에서 빌드 시점에 LANGSMITH_KEY 파일로 떨어뜨리고, 번들 스크립트가
# 그걸 복사한다(VERSION 파일과 완전히 같은 패턴). 소스 실행(dev) 환경은 .env의
# LANGCHAIN_API_KEY(저자 본인 키)로 폴백 — 이건 이미 있던 값이라 새로 건드릴 게 없다.

import os
import platform
import sqlite3
import uuid
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

APP_DB_PATH = "data/app.db"

# 저자 본인 "AIsaac" 프로젝트(.env 개발용)와 안 섞이게 별도 프로젝트로 분리.
LANGSMITH_PROJECT = "AIsaac-community"

SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    consent INTEGER NOT NULL DEFAULT 0,
    install_id TEXT NOT NULL,
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


def get_status(*, conn: sqlite3.Connection | None = None) -> dict:
    """단일 행(id=1)만 쓴다 — 1인 1설치라 여러 행이 필요 없다.

    **행이 없다는 것 자체가 "아직 동의를 물어본 적 없음"이다**(08-09, 첫 실행 안내창을
    붙이면서 도입). 첫 조회 때 consent=0 행을 만들던 원래 방식으로는 "안 물어봄"과
    "물어봤는데 거부함"이 둘 다 consent=0이라 구분이 안 됐고, 그러면 거부한 사용자에게
    앱을 켤 때마다 안내창이 다시 뜬다 — 동의를 받는 게 아니라 승낙할 때까지 조르는
    꼴이라 옵트인 자체가 무의미해진다.

    구분 방법으로 asked_at 컬럼을 더하는 안 대신 행 존재 여부를 쓴 이유는 마이그레이션이다
    — CREATE TABLE IF NOT EXISTS는 이미 있는 테이블에 컬럼을 못 붙여서 ALTER TABLE 경로를
    따로 둬야 하는데, 행 존재로 판정하면 스키마가 그대로다.

    그래서 조회는 절대 행을 만들지 않는다. install_id 발급은 set_consent()로 미뤘다 —
    끝까지 대답하지 않은 설치에 식별자를 발급하지 않는 쪽이 이 기능의 취지에도 맞다.
    """
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        row = conn.execute("SELECT * FROM telemetry WHERE id = 1").fetchone()
        if row is None:
            return {"asked": False, "consent": False, "install_id": None}
        return {"asked": True, "consent": bool(row["consent"]), "install_id": row["install_id"]}
    finally:
        if owns_conn:
            conn.close()


def set_consent(consent: bool, *, conn: sqlite3.Connection | None = None) -> dict:
    """동의·거부를 기록한다. **거부(False)도 반드시 행을 남긴다** — 행 없음이 곧
    "아직 안 물어봄"이라, 거부를 기록하지 않으면 다음 실행에서 또 묻게 된다."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        install_id = get_status(conn=conn)["install_id"] or str(uuid.uuid4())
        # UPSERT — 행이 없으면 INSERT(install_id 최초 발급), 있으면 consent·updated_at만
        # 갱신한다. install_id는 갱신 대상에서 뺐다: 껐다 켜도 같은 설치로 집계돼야 한다.
        # `excluded`는 SQLite가 "INSERT하려다 충돌난 그 행"에 붙여주는 이름이다.
        conn.execute(
            """
            INSERT INTO telemetry (id, consent, install_id, updated_at) VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET consent = excluded.consent, updated_at = excluded.updated_at
            """,
            (1 if consent else 0, install_id, _now()),
        )
        conn.commit()
        return {"asked": True, "consent": consent, "install_id": install_id}
    finally:
        if owns_conn:
            conn.close()


def _resolve_langsmith_key() -> str | None:
    key_file = Path("LANGSMITH_KEY")
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    return os.environ.get("LANGCHAIN_API_KEY")


def _app_version() -> str:
    version_file = Path("VERSION")
    return version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "dev"


def tracing_scope():
    """동의 + 키가 둘 다 있을 때만 실제 LangSmith 트레이싱 컨텍스트를, 아니면
    아무 일도 안 하는 nullcontext를 돌려준다 — 호출부는 동의 여부를 직접 안 따지고
    항상 `with telemetry.tracing_scope():`로만 감싸면 된다. 동의는 있어도 키가 없는
    경우(소스 실행 중 .env에 LANGCHAIN_API_KEY가 없는 상태 등)는 조용히 무시한다 —
    사용자가 명시적으로 끈 게 아니라 환경이 안 갖춰진 것뿐이라 에러로 취급 안 함."""
    status = get_status()
    if not status["consent"]:
        return nullcontext()
    key = _resolve_langsmith_key()
    if not key:
        return nullcontext()

    from langchain_core.tracers.context import tracing_v2_enabled
    from langsmith import Client as LangSmithClient

    tags = [platform.system(), _app_version(), status["install_id"]]
    return tracing_v2_enabled(
        project_name=LANGSMITH_PROJECT,
        client=LangSmithClient(api_key=key),
        tags=tags,
    )
