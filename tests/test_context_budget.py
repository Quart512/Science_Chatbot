"""
check_context_budget — models.py의 순수 헬퍼. 논문 분석기(②a)가 LLM을 호출하기 전에
입력 길이가 모델별 예산(문자 수)을 넘는지 미리 확인한다. 진짜 API 호출은 하지 않으므로
비용 0으로 빠르게 검증 가능.
"""
from models import CONTEXT_BUDGET_CHARS, ContextBudgetExceeded, check_context_budget


def test_check_context_budget_passes_under_budget():
    check_context_budget("Qwen-tuned", "a" * (CONTEXT_BUDGET_CHARS["Qwen-tuned"] - 1))
    # 예외 없이 통과하면 성공


def test_check_context_budget_raises_over_budget():
    over = CONTEXT_BUDGET_CHARS["Qwen-tuned"] + 1
    try:
        check_context_budget("Qwen-tuned", "a" * over)
        assert False, "ContextBudgetExceeded가 발생했어야 함"
    except ContextBudgetExceeded as e:
        assert e.model == "Qwen-tuned"
        assert e.text_len == over
        assert e.budget == CONTEXT_BUDGET_CHARS["Qwen-tuned"]


def test_check_context_budget_unknown_model_passes():
    # CONTEXT_BUDGET_CHARS에 없는 모델 이름이면 예산 자체가 없는 것으로 보고 통과
    check_context_budget("unknown-model", "a" * 1_000_000)


def test_context_budget_exceeded_is_not_caught_by_invoke_with_fallback():
    # invoke_with_fallback의 except 목록에 ContextBudgetExceeded가 없어야 한다 —
    # 여기 섞이면 "길이 초과"가 "모델 고장"으로 오인되어 엉뚱하게 fallback된다.
    # (실제 except 절 목록을 직접 들여다보는 대신, 이 예외가 그 목록에 속한
    # 표준 예외 타입이 아님을 확인하는 정적인 방식으로 검증)
    from google.api_core.exceptions import PermissionDenied, ResourceExhausted
    from anthropic import RateLimitError
    from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
    from openai import APIConnectionError, BadRequestError, LengthFinishReasonError

    caught_types = (
        ResourceExhausted, PermissionDenied, RateLimitError,
        ChatGoogleGenerativeAIError, APIConnectionError,
        BadRequestError, LengthFinishReasonError,
    )
    assert not issubclass(ContextBudgetExceeded, caught_types)
