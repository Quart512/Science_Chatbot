"""
telemetry.py — 지인 테스트 사용 데이터 공유 동의(08-09). api_keys.py와 같은 패턴,
:memory: sqlite3 연결로 순수 로직만 검증. tracing_scope()가 실제로 LangSmith에 붙는지는
네트워크가 필요해 여기서 검증 안 함 — nullcontext vs 실제 컨텍스트 매니저 반환 여부만 확인.
"""
import sqlite3
from contextlib import nullcontext
from pathlib import Path

import pytest

import telemetry


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    telemetry.init_schema(c)
    yield c
    c.close()


def test_get_status_does_not_create_row_and_reports_not_asked(conn):
    """조회만으로는 행이 생기면 안 된다 — 행 없음이 곧 "아직 동의를 안 물어봄"이라,
    조회가 행을 만들면 첫 실행 안내창을 띄울 근거가 사라진다."""
    status = telemetry.get_status(conn=conn)
    assert status["asked"] is False
    assert status["consent"] is False
    assert status["install_id"] is None
    assert conn.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0] == 0


def test_set_consent_true_persists_and_marks_asked(conn):
    telemetry.set_consent(True, conn=conn)
    status = telemetry.get_status(conn=conn)
    assert status["consent"] is True
    assert status["asked"] is True
    assert status["install_id"]  # 동의 시점에 uuid4가 발급돼 있어야 함


def test_set_consent_false_also_marks_asked(conn):
    """거부도 반드시 기록돼야 한다 — 이게 안 남으면 거부한 사용자에게 앱을 켤 때마다
    안내창이 다시 떠서 옵트인 동의가 무의미해진다(이 기능 전체가 걸린 계약)."""
    telemetry.set_consent(False, conn=conn)
    status = telemetry.get_status(conn=conn)
    assert status["asked"] is True
    assert status["consent"] is False


def test_set_consent_preserves_install_id(conn):
    before = telemetry.set_consent(True, conn=conn)
    telemetry.set_consent(False, conn=conn)
    after = telemetry.get_status(conn=conn)
    assert after["install_id"] == before["install_id"]


def test_set_consent_false_after_true(conn):
    telemetry.set_consent(True, conn=conn)
    telemetry.set_consent(False, conn=conn)
    assert telemetry.get_status(conn=conn)["consent"] is False


def test_resolve_langsmith_key_prefers_bundle_file(monkeypatch, tmp_path):
    key_file = tmp_path / "LANGSMITH_KEY"
    key_file.write_text("ls-from-file\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LANGCHAIN_API_KEY", "ls-from-env")

    assert telemetry._resolve_langsmith_key() == "ls-from-file"


def test_resolve_langsmith_key_falls_back_to_env_when_no_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LANGCHAIN_API_KEY", "ls-from-env")

    assert telemetry._resolve_langsmith_key() == "ls-from-env"


def test_resolve_langsmith_key_none_when_neither_present(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

    assert telemetry._resolve_langsmith_key() is None


def test_tracing_scope_is_noop_when_consent_off(monkeypatch):
    monkeypatch.setattr(telemetry, "get_status", lambda: {"asked": True, "consent": False, "install_id": "x"})
    scope = telemetry.tracing_scope()
    assert isinstance(scope, nullcontext)


def test_tracing_scope_is_noop_when_consent_on_but_no_key(monkeypatch):
    monkeypatch.setattr(telemetry, "get_status", lambda: {"asked": True, "consent": True, "install_id": "x"})
    monkeypatch.setattr(telemetry, "_resolve_langsmith_key", lambda: None)
    scope = telemetry.tracing_scope()
    assert isinstance(scope, nullcontext)


def test_tracing_scope_returns_real_context_when_consent_and_key_present(monkeypatch):
    monkeypatch.setattr(telemetry, "get_status", lambda: {"asked": True, "consent": True, "install_id": "install-xyz"})
    monkeypatch.setattr(telemetry, "_resolve_langsmith_key", lambda: "ls-fake-key")
    scope = telemetry.tracing_scope()
    # nullcontext가 아니라 실제 tracing_v2_enabled()의 컨텍스트 매니저여야 한다 —
    # __enter__는 안 부른다(네트워크 클라이언트를 실제로 안 돌려도 되게).
    assert not isinstance(scope, nullcontext)
