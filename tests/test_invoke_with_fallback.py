"""
invoke_with_fallback — models.py의 재귀적 fallback 로직.
실제 LLM 클라이언트(model_map의 값들)를 가짜로 바꿔치기해서, 진짜 API 호출 없이
"어떤 모델을 먼저 쓰고, 실패하면 다음 모델로 넘어가고, 다 실패하면 에러를 내는가"
라는 로직만 검증한다.

model_map 자체를 통째로 monkeypatch — models.py 코드는 이 사실을 전혀 모른다
(테스트 개념이 운영 코드에 스며들지 않음). graph.py를 거치지 않고 models를 바로
import하므로 retrieval의 무거운 import-time 로딩과도 아예 무관하다.

08-05부터 model_map의 값은 클라이언트 객체가 아니라 "클라이언트를 만드는 함수"다
(설정 화면 착수 — models.py의 model_map 주석 참고) — invoke_with_fallback이
model_map[name]()으로 호출하므로, 여기서도 가짜 클라이언트를 반환하는 lambda로
감싸야 한다.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from anthropic import BadRequestError as AnthropicBadRequestError
from google.api_core.exceptions import ResourceExhausted
from google.genai.errors import ServerError

import models


def _anthropic_bad_request(message: str) -> AnthropicBadRequestError:
    resp = httpx.Response(
        400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        json={"error": {"message": message}},
    )
    return AnthropicBadRequestError(message, response=resp, body={"error": {"message": message}})


def make_fake_model(*, raises=None):
    """invoke()가 raises 없이는 더미 응답을, raises가 주어지면 그 예외를 던지는 가짜 모델 클라이언트."""
    fake = MagicMock()
    if raises is not None:
        fake.invoke.side_effect = raises
    else:
        fake.invoke.return_value = SimpleNamespace(
            content="더미 답변",
            usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        )
    return fake


def test_success_on_first_try(monkeypatch):
    fake_gemini = make_fake_model()
    monkeypatch.setattr(models, "model_map", {"gemini": lambda: fake_gemini, "claude": lambda: make_fake_model()})

    response, used_model, disabled, tokens = models.invoke_with_fallback("gemini", messages=["dummy"])

    assert used_model == "gemini"
    assert disabled == []
    assert tokens == {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
    fake_gemini.invoke.assert_called_once()


def test_falls_back_to_secondary_on_resource_exhausted(monkeypatch):
    fake_gemini = make_fake_model(raises=ResourceExhausted("quota exceeded"))
    fake_claude = make_fake_model()
    monkeypatch.setattr(models, "model_map", {"gemini": lambda: fake_gemini, "claude": lambda: fake_claude})

    response, used_model, disabled, tokens = models.invoke_with_fallback("gemini", messages=["dummy"])

    assert used_model == "claude"
    assert disabled == ["gemini"]  # 실패한 모델이 기록됨
    fake_claude.invoke.assert_called_once()


def test_falls_back_on_google_genai_server_error(monkeypatch):
    # 08-11② 실사용 중 발견 — langchain_google_genai가 내부적으로 google-genai SDK로
    # 갈아탄 뒤로 과부하(503) 시 ChatGoogleGenerativeAIError가 아니라 이 SDK의
    # ServerError가 그대로 올라온다. 예전 예외 화이트리스트로는 못 잡아 fallback을
    # 못 타고 500까지 샜던 실제 사례(models.py의 GoogleGenAIAPIError 주석 참고).
    fake_gemini = make_fake_model(raises=ServerError(503, {"error": {"message": "overloaded"}}))
    fake_claude = make_fake_model()
    monkeypatch.setattr(models, "model_map", {"gemini": lambda: fake_gemini, "claude": lambda: fake_claude})

    response, used_model, disabled, tokens = models.invoke_with_fallback("gemini", messages=["dummy"])

    assert used_model == "claude"
    assert disabled == ["gemini"]
    fake_claude.invoke.assert_called_once()


def test_falls_back_on_anthropic_credit_balance_error(monkeypatch):
    # 08-11② 실사용 중 발견 — anthropic 계정 크레딧 부족도 anthropic.BadRequestError(400)로
    # 온다. openai.BadRequestError(이미 화이트리스트에 있음)와 이름은 같지만 서로 다른
    # SDK의 별개 클래스라 따로 잡아야 한다(models.py의 AnthropicBadRequestError 주석 참고).
    fake_claude = make_fake_model(raises=_anthropic_bad_request("credit balance too low"))
    fake_gemini = make_fake_model()
    monkeypatch.setattr(models, "model_map", {"claude": lambda: fake_claude, "gemini": lambda: fake_gemini})

    response, used_model, disabled, tokens = models.invoke_with_fallback("claude", messages=["dummy"])

    assert used_model == "gemini"
    assert disabled == ["claude"]
    fake_gemini.invoke.assert_called_once()


def test_raises_runtime_error_when_all_models_exhausted(monkeypatch):
    fake_gemini = make_fake_model(raises=ResourceExhausted("quota exceeded"))
    fake_claude = make_fake_model(raises=ResourceExhausted("quota exceeded"))
    monkeypatch.setattr(models, "model_map", {"gemini": lambda: fake_gemini, "claude": lambda: fake_claude})

    with pytest.raises(RuntimeError):
        models.invoke_with_fallback("gemini", messages=["dummy"])


def test_disabled_models_are_skipped_without_calling_invoke(monkeypatch):
    fake_gemini = make_fake_model()
    fake_claude = make_fake_model()
    monkeypatch.setattr(models, "model_map", {"gemini": lambda: fake_gemini, "claude": lambda: fake_claude})

    response, used_model, disabled, tokens = models.invoke_with_fallback(
        "gemini", messages=["dummy"], disabled_models=["gemini"]
    )

    assert used_model == "claude"
    fake_gemini.invoke.assert_not_called()  # 이미 disabled면 애초에 시도조차 안 함
