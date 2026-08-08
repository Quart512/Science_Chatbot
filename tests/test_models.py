# models.py의 클라이언트 팩토리(model_map) — 저장된 키도 .env도 없을 때 pydantic
# ValidationError(서드파티 라이브러리 내부 에러, FALLBACK_EXCEPTIONS 밖이라 못 잡힘) 대신
# MissingAPIKeyError를 먼저 던지는 계약만 검증한다(08-06, 포터블 번들 실기 테스트로 발견
# 한 버그의 회귀 방지). 실제 클라이언트 생성·네트워크 호출은 없음.

import pytest

import api_keys
import models
from models import MissingAPIKeyError, REQUEST_SCOPED_EXCEPTIONS, model_map


def test_missing_api_key_error_is_request_scoped_not_session_outage():
    # 08-08 — v0.1.2 실사용에서 발견한 버그의 회귀 테스트. 예전엔 SESSION_OUTAGE_EXCEPTIONS라
    # disabled_models(체크포인트 저장, 스레드 내내 유지)에 올라, 설정 화면에서 키를 입력한
    # 뒤에도 같은 스레드에서는 계속 막혔다(다시 열어주는 경로가 없어서). MissingAPIKeyError는
    # model_map[name]() 생성 단계(네트워크 호출 전)에서 나는 예외라 매 턴 다시 확인해도
    # 비용이 0이므로, REQUEST_SCOPED_EXCEPTIONS로 옮겨 매번 다시 확인하게 했다 — 여전히
    # invoke_with_fallback의 FALLBACK_EXCEPTIONS 안이라 다른 모델로 폴백은 그대로 된다.
    assert issubclass(MissingAPIKeyError, REQUEST_SCOPED_EXCEPTIONS)
    assert issubclass(MissingAPIKeyError, models.FALLBACK_EXCEPTIONS)


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
