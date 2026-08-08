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
from google.genai.errors import ClientError, ServerError
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError

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
    # 08-05: 원래 여기서 disabled == ["gemini"]를 단언했으나, 503은 몇 초 뒤 풀리는 일시
    # 장애라 세션 차단 대상이 아니라고 판단해 동작을 바꿨다(아래
    # test_google_503_is_transient_and_does_not_disable가 그 계약을 직접 검증). 이 테스트가
    # 원래 지키려던 것은 "ServerError에 fallback이 걸린다"이므로 그 단언만 남긴다.
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


# --- 아래 5개: 08-05 "세션 지속 장애 vs 이번 요청 한정 실패" 구분 (models.py의 예외 튜플 주석 참고) ---
# 08-05 관심사 등록 버그의 근본 원인 — 예외 종류를 안 가리고 실패한 모델을 전부
# disabled_models에 넣는 바람에, 요청 형식 하나가 틀린 것만으로 사용자가 고른 모델이
# 그 스레드 내내 조용히 회피됐다. fallback 자체는 옳았으므로 그건 그대로 두고,
# "세션 상태를 오염시키느냐"만 갈랐다는 게 이 테스트들의 요지.


def test_request_scoped_failure_falls_back_without_disabling(monkeypatch):
    # gemini가 이 요청의 형식을 거부(INVALID_ARGUMENT)한 경우 — claude는 같은 메시지를
    # 받아들이므로(prefill 허용) fallback은 성공해야 하고, 동시에 gemini는 세션 차단
    # 목록에 들어가면 안 된다(다음 턴엔 정상적으로 다시 시도돼야 한다).
    fake_gemini = make_fake_model(raises=ChatGoogleGenerativeAIError(
        "400 INVALID_ARGUMENT: Requests ending with a model turn are not supported"
    ))
    fake_claude = make_fake_model()
    monkeypatch.setattr(models, "model_map", {"gemini": lambda: fake_gemini, "claude": lambda: fake_claude})

    _response, used_model, disabled, _tokens = models.invoke_with_fallback("gemini", messages=["dummy"])

    assert used_model == "claude"          # fallback은 여전히 동작
    assert disabled == []                  # 핵심 — 세션 차단 목록이 안 더러워진다
    fake_claude.invoke.assert_called_once()


def test_google_503_is_transient_and_does_not_disable(monkeypatch):
    # 과부하(503)는 몇 초 뒤 풀리는 일시 장애다 — 한 번의 blip으로 세션 내내 gemini를
    # 못 쓰게 되면 안 된다. 08-11에 추가한 "503은 fallback을 탄다"는 그대로 유지.
    fake_gemini = make_fake_model(raises=ServerError(503, {"error": {"message": "overloaded"}}))
    fake_claude = make_fake_model()
    monkeypatch.setattr(models, "model_map", {"gemini": lambda: fake_gemini, "claude": lambda: fake_claude})

    _response, used_model, disabled, _tokens = models.invoke_with_fallback("gemini", messages=["dummy"])

    assert used_model == "claude"
    assert disabled == []


def test_google_429_quota_does_disable(monkeypatch):
    # 같은 SDK·같은 예외 클래스라도 429(쿼터 소진)는 리필 전까진 계속 실패하므로
    # 세션 차단이 맞다 — HTTP 코드로 가른다는 설계가 실제로 두 방향 다 작동하는지.
    fake_gemini = make_fake_model(raises=ClientError(429, {"error": {"message": "quota exceeded"}}))
    fake_claude = make_fake_model()
    monkeypatch.setattr(models, "model_map", {"gemini": lambda: fake_gemini, "claude": lambda: fake_claude})

    _response, used_model, disabled, _tokens = models.invoke_with_fallback("gemini", messages=["dummy"])

    assert used_model == "claude"
    assert disabled == ["gemini"]


def test_anthropic_malformed_request_does_not_disable(monkeypatch):
    # 크레딧 부족(위 test_falls_back_on_anthropic_credit_balance_error)과 **같은 클래스**로
    # 오는 잘못된 요청. 메시지로만 구분되므로, 크레딧 문구가 없으면 세션 차단을 하지
    # 않는 쪽(안전한 기본값)으로 떨어져야 한다.
    fake_claude = make_fake_model(raises=_anthropic_bad_request("messages: at least one message is required"))
    fake_gemini = make_fake_model()
    monkeypatch.setattr(models, "model_map", {"claude": lambda: fake_claude, "gemini": lambda: fake_gemini})

    _response, used_model, disabled, _tokens = models.invoke_with_fallback("claude", messages=["dummy"])

    assert used_model == "gemini"
    assert disabled == []


def test_request_scoped_failure_on_every_model_terminates(monkeypatch):
    # 세션 차단을 안 하게 되면서 생긴 새 위험 — 예전엔 disabled_models가 "이미 시도함"
    # 역할을 겸해서 재귀가 멈췄다. 그 둘을 분리했으니(_attempted) 요청 한정 실패가 전
    # 모델에서 나도 무한 재귀 없이 끝나야 하고, 에러 메시지에 모델별 실패 사유가 남아
    # "왜 전부 실패했는지"를 호출부가 알 수 있어야 한다.
    fake_gemini = make_fake_model(raises=ChatGoogleGenerativeAIError("400 INVALID_ARGUMENT"))
    fake_claude = make_fake_model(raises=ChatGoogleGenerativeAIError("400 INVALID_ARGUMENT"))
    monkeypatch.setattr(models, "model_map", {"gemini": lambda: fake_gemini, "claude": lambda: fake_claude})

    with pytest.raises(models.AllModelsFailedError) as excinfo:
        models.invoke_with_fallback("gemini", messages=["dummy"])

    message = str(excinfo.value)
    assert "gemini" in message and "claude" in message
    assert "INVALID_ARGUMENT" in message   # 진짜 원인이 안 사라진다
    assert excinfo.value.__cause__ is not None  # raise ... from exc 로 원본 예외가 체인됨
    # disabled_models 정밀화(08-06) — 요청 한정 실패뿐이었으니 새로 세션 차단할 모델이
    # 없다. 호출부(graph.py)가 이걸 그대로 써서 "전부 실패=세션 전체 차단"을 피한다.
    assert excinfo.value.disabled_models == []


def test_client_construction_failure_falls_back(monkeypatch):
    # 08-06 실기 발견 — model_map[name]()(클라이언트 생성)이 원래 try 블록 "밖"에 있어서
    # MissingAPIKeyError(생성 시점에 남, invoke() 호출 전) 같은 FALLBACK_EXCEPTIONS가
    # 못 잡고 그대로 새어나갔다(포터블 번들에 .env가 없어 실사용에서 실제로 걸림).
    # 여기선 gemini의 "생성 함수 자체"가 실패하도록 만들어 재현·회귀 방지한다.
    def _boom():
        raise models.MissingAPIKeyError("gemini")
    fake_claude = make_fake_model()
    monkeypatch.setattr(models, "model_map", {"gemini": _boom, "claude": lambda: fake_claude})

    response, used_model, disabled, tokens = models.invoke_with_fallback("gemini", messages=["dummy"])

    assert used_model == "claude"
    # 08-08 — MissingAPIKeyError는 REQUEST_SCOPED_EXCEPTIONS로 옮겼다(아래 함수의
    # 갱신된 주석 참고) — 세션 차단 안 함, 다음 턴엔 gemini를 다시 시도한다.
    assert disabled == []
    fake_claude.invoke.assert_called_once()


def test_client_construction_failure_on_every_model_raises_with_detail(monkeypatch):
    def _boom_gemini():
        raise models.MissingAPIKeyError("gemini")
    def _boom_claude():
        raise models.MissingAPIKeyError("claude")
    monkeypatch.setattr(models, "model_map", {"gemini": _boom_gemini, "claude": _boom_claude})

    with pytest.raises(models.AllModelsFailedError) as excinfo:
        models.invoke_with_fallback("gemini", messages=["dummy"])

    message = str(excinfo.value)
    assert "gemini" in message and "claude" in message
    assert "API 키" in message
    # 08-08 — MissingAPIKeyError를 REQUEST_SCOPED_EXCEPTIONS로 재분류했다(아래 참고).
    # 그 결과 disabled_models(체크포인트에 저장돼 세션 내내 남는 값)엔 아무것도 안 실린다
    # — 이 실패가 "이번 요청 한정"이라는 뜻이고, 다음 턴엔 두 모델 다시 시도한다.
    #
    # 재분류 이유: 원래 SESSION_OUTAGE_EXCEPTIONS였던 근거("사용자가 설정에서 넣기
    # 전엔 계속 실패")는 맞았지만 "그 뒤엔 더는 실패 안 한다"는 반대쪽을 놓쳤다 —
    # v0.1.2 실사용에서 실제로 겪음: 키 없이 챗을 시도해 disabled_models에 오른 뒤,
    # 같은 세션에서 설정 화면에 키를 입력해도 그 스레드는 계속 막혔다(체크포인트에
    # 박힌 disabled_models를 다시 열어주는 경로가 없어서 — 새 스레드로 가야만 풀렸다).
    # 세션 차단이 원래 아끼려던 건 "실패할 걸 아는 API 호출"인데, MissingAPIKeyError는
    # `model_map[name]()` 생성 단계(네트워크 호출 전)에서 나는 예외라 매 턴 다시
    # 확인해도 비용이 0이다 — 그러니 기억해 둘 값어치가 없고, 매 턴 다시 확인하는
    # 쪽이 공짜로 더 낫다(키가 여전히 없으면 즉시 같은 실패, 생겼으면 바로 성공).
    assert excinfo.value.disabled_models == []


def test_disabled_models_are_skipped_without_calling_invoke(monkeypatch):
    fake_gemini = make_fake_model()
    fake_claude = make_fake_model()
    monkeypatch.setattr(models, "model_map", {"gemini": lambda: fake_gemini, "claude": lambda: fake_claude})

    response, used_model, disabled, tokens = models.invoke_with_fallback(
        "gemini", messages=["dummy"], disabled_models=["gemini"]
    )

    assert used_model == "claude"
    fake_gemini.invoke.assert_not_called()  # 이미 disabled면 애초에 시도조차 안 함
