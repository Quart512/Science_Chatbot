# models.py의 클라이언트 팩토리(model_map) — 저장된 키도 .env도 없을 때 pydantic
# ValidationError(서드파티 라이브러리 내부 에러, FALLBACK_EXCEPTIONS 밖이라 못 잡힘) 대신
# MissingAPIKeyError를 먼저 던지는 계약만 검증한다(08-06, 포터블 번들 실기 테스트로 발견
# 한 버그의 회귀 방지). 실제 클라이언트 생성·네트워크 호출은 없음.

import pytest

import api_keys
import models
from models import MissingAPIKeyError, SESSION_OUTAGE_EXCEPTIONS, model_map


def test_missing_api_key_error_is_a_session_outage_exception():
    # invoke_with_fallback이 이 예외를 잡아 다른 모델로 폴백하려면 여기 속해 있어야 한다.
    assert issubclass(MissingAPIKeyError, SESSION_OUTAGE_EXCEPTIONS)


def test_gemini_client_raises_missing_api_key_error_without_any_key(monkeypatch):
    monkeypatch.setattr(api_keys, "get_api_key", lambda provider: None)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(MissingAPIKeyError):
        model_map["gemini"]()


def test_claude_client_raises_missing_api_key_error_without_any_key(monkeypatch):
    monkeypatch.setattr(api_keys, "get_api_key", lambda provider: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(MissingAPIKeyError):
        model_map["claude"]()


def test_gemini_client_does_not_raise_when_env_var_present(monkeypatch):
    # .env 폴백 경로(저장된 키는 없지만 환경변수는 있음)는 그대로 통과해야 한다 —
    # 실제 클라이언트 생성까지는 확인하되 네트워크 호출은 안 함.
    monkeypatch.setattr(api_keys, "get_api_key", lambda provider: None)
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy-for-test")

    model_map["gemini"]()  # 예외 없이 생성만 되면 통과
