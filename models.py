#모델 선택 기능을 위한 map
import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

import api_keys

from google.api_core.exceptions import ResourceExhausted, PermissionDenied  # 결제 계정 정지 등 403
from google.genai.errors import APIError as GoogleGenAIAPIError  # ClientError/ServerError(예: 503) 공통 부모
from anthropic import RateLimitError
from anthropic import BadRequestError as AnthropicBadRequestError  # 크레딧 부족도 400으로 옴 — openai.BadRequestError와 이름만 같은 별개 클래스
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from openai import APIConnectionError  # 로컬 llama-server 접속 에러
from openai import BadRequestError
from openai import LengthFinishReasonError

import sys
import traceback
#api key 가져오기
load_dotenv()

# tokens_used 누적 헬퍼. new(provider의 usage_metadata)는 통제 밖 값이라 .get(..., 0)으로
# 방어하고, 이 세 스칼라 키만 더한다 — provider별 중첩 세부 항목(dict)까지 합치면 타입 에러.
# 원래 graph.py에 있었는데 연구 워크플로우·참고문헌 추천기까지 세 곳이 같은 코드를 갖게 돼
# 여기로 올렸다(토큰은 모델 호출의 부산물이라 "모델 정책은 models.py 단일 지점" 규칙에 맞음).
TOKEN_KEYS = ("input_tokens", "output_tokens", "total_tokens")

EMPTY_TOKENS = {k: 0 for k in TOKEN_KEYS}


def add_tokens(current: dict, new: dict) -> dict:
    return {k: current.get(k, 0) + new.get(k, 0) for k in TOKEN_KEYS}


# model_map의 값은 클라이언트 "생성 함수"다(08-05, 설정 화면 착수 전까진 이미 만들어진
# 클라이언트 객체였다) — 예전 방식은 모듈이 임포트되는 순간 그 시점의 환경변수로 API
# 키가 영구히 고정돼서, 사용자가 설정 화면에서 키를 입력해도 서버를 재시작하기 전엔
# 절대 반영이 안 됐다. invoke_with_fallback()이 매 호출마다 이 함수를 불러 클라이언트를
# 새로 만든다 — 캐시는 안 둔다(LangChain 클라이언트 생성은 실제 연결 없이 설정 객체만
# 만드는 거라 가볍고, 캐시를 두면 "키를 바꿨는데 이전 클라이언트가 남아있다"는 무효화
# 버그가 새로 생길 뿐이다 — "단순 경로부터").
def _gemini_client():
    # api_keys(DB)에 저장된 값이 있으면 최우선, 없으면 인자를 아예 안 넘겨 라이브러리가
    # 알아서 환경변수(GOOGLE_API_KEY)를 읽게 한다(.env 폴백 — os.getenv를 직접 안 읽고
    # 위임하는 이유: 라이브러리가 이미 하는 일을 다시 구현하지 않기 위함).
    saved_key = api_keys.get_api_key("gemini")
    kwargs = {"google_api_key": saved_key} if saved_key else {}
    # flash-lite가 무료 티어 일일 한도가 훨씬 높음(구글 공식 문서 확인, 2026-07)
    return ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", **kwargs)


def _claude_client():
    saved_key = api_keys.get_api_key("claude")
    kwargs = {"anthropic_api_key": saved_key} if saved_key else {}
    return ChatAnthropic(model="claude-haiku-4-5-20251001", **kwargs)


def _qwen_tuned_client():
    # 파인튜닝한 Qwen2.5-1.5B(Q4_K_M GGUF)를 로컬 llama-server(OpenAI 호환)로 서빙.
    # 서버 꺼져 있어도 클라이언트 생성 자체는 안전(접속은 invoke 시점) — 로컬 서버라
    # api_keys 저장소를 안 거친다(SUPPORTED_PROVIDERS에도 없음).
    # 서버 실행: llama-server -m models/qwen_finetuned_Q4_K_M.gguf --port 8080
    return ChatOpenAI(
        base_url=os.getenv("LOCAL_MODEL_URL", "http://localhost:8080/v1"),  # docker-compose면 llama-server:8080
        api_key="not-needed",  # 로컬 서버는 키 검사 안 함(필드가 필수라 더미값)
        max_tokens=10000,
        frequency_penalty=0.3,
        model=os.getenv("LOCAL_MODEL_NAME", "qwen-tuned"),
    )


model_map = {
    "gemini": _gemini_client,
    "claude": _claude_client,
    "Qwen-tuned": _qwen_tuned_client,
}

# 모델별 컨텍스트 예산(문자 수 기준 — ingest.py/paper_chunking.py의 길이 기준과 통일,
# 토크나이저 단위 정밀도는 불필요). 논문 분석기(②a)가 LLM 호출 전 입력 길이를 미리
# 체크하는 데 쓴다. Qwen-tuned(로컬 llama-server, ctx 4096)만 실제로 걸릴 수 있는 값 —
# 나머지는 대략치이니 초과가 관측되면 여기만 조정.
CONTEXT_BUDGET_CHARS: dict[str, int] = {
    "gemini": 2_000_000,
    "claude": 150_000,
    "Qwen-tuned": 6_000,
}

# 오케스트레이터(orchestrator.py)의 멀티턴 대화 이력 트리밍용 — CONTEXT_BUDGET_CHARS를
# 그대로 쓰지 않고 절반만 떼어둔다(대략치, 08-13 착수 시 정한 값이라 실측 후 조정 가능).
# 대화 이력이 예산 전체를 차지하면 같은 호출에 실리는 검색 문서·tool 결과가 들어갈
# 자리가 없어지므로, 모델 전체 예산과는 별도로 "질문+답변 역사"만을 위한 몫을 둔다.
MESSAGE_HISTORY_BUDGET_CHARS: dict[str, int] = {model: budget // 2 for model, budget in CONTEXT_BUDGET_CHARS.items()}


class ContextBudgetExceeded(Exception):
    """모델별 컨텍스트 예산 초과 예외. invoke_with_fallback()의 fallback 대상 목록에는
    일부러 안 넣는다 — "너무 길어서 실패"를 "모델 고장"으로 오인해 fallback해도 다음
    모델 역시 길이 때문에 똑같이 실패한다. API 호출 "전에" 체크하므로 비용은 0."""

    def __init__(self, model: str, text_len: int, budget: int):
        self.model = model
        self.text_len = text_len
        self.budget = budget
        super().__init__(
            f"'{model}' 컨텍스트 예산({budget:,}자) 초과 — 입력 길이 {text_len:,}자. "
            "분할(map-reduce)은 아직 미구현 — 조용히 자르지 않고 정직하게 실패."
        )


def check_context_budget(model: str, text: str) -> None:
    """model로 text를 보내기 전에 길이가 예산 안에 드는지 확인한다. 초과 시
    ContextBudgetExceeded — 호출부가 "요약 불가" 같은 정직한 실패로 전달. 예산이
    없는 model 이름이면 통과."""
    budget = CONTEXT_BUDGET_CHARS.get(model)
    if budget is not None and len(text) > budget:
        raise ContextBudgetExceeded(model, len(text), budget)


# fallback을 태울 예외들. 세 갈래로 나눈 축은 "요청 오류냐 모델 장애냐"가 아니라
# **"세션 내내 지속되는 장애냐, 이번 요청 한정 실패냐"**다(08-05에 축을 바꿈).
#
# 원래는 아래 세 튜플이 하나로 합쳐져 있었고, 무엇이 걸리든 실패한 모델을 곧장
# disabled_models에 넣었다. 그래서 "이번 요청에서 실패했다"가 "이 세션에서 이 모델은
# 죽었다"로 승격됐다 — 08-05 관심사 등록 버그의 실제 피해가 이것이다(gemini가 메시지
# 형식을 거부했을 뿐인데 그 스레드의 이후 물리 QA 턴까지 gemini가 통째로 회피됐다).
#
# 처음엔 "요청 오류는 fallback도 하지 말고 그대로 올려보내자"고 봤는데 확인해보니 틀렸다.
# fallback은 세 경우 다 실제로 맞는 복구다 — ① gemini의 INVALID_ARGUMENT("model 턴으로
# 끝나는 메시지")는 claude가 허용하므로(prefill) 넘기면 성공하고, ② LengthFinishReasonError는
# CONTEXT_BUDGET_CHARS가 모델마다 달라서(Qwen 6,000자 vs gemini 2,000,000자) 큰 모델로
# 넘기는 게 정확한 복구이며, ③ anthropic 크레딧 부족과 잘못된 요청은 애초에 같은 클래스로
# 온다. 그러니 바꿔야 할 건 fallback 여부가 아니라 **세션 상태를 오염시키느냐**뿐이다.
SESSION_OUTAGE_EXCEPTIONS = (
    ResourceExhausted,      # 429 쿼터 소진 — 리필 전까진 계속 실패
    PermissionDenied,       # 403 결제 계정 정지 등
    RateLimitError,         # anthropic 429
    APIConnectionError,     # 로컬 llama-server가 안 떠 있음 — 세션 중에 켜질 일이 드묾
)

# fallback은 타되 세션 차단은 안 하는 것들 — 다음 턴엔 사용자가 고른 모델을 다시 시도한다.
REQUEST_SCOPED_EXCEPTIONS = (
    ChatGoogleGenerativeAIError,  # INVALID_ARGUMENT 등 이 요청의 형식 문제
    BadRequestError,              # openai(=로컬 llama-server) 400
    LengthFinishReasonError,      # 이 요청이 이 모델 컨텍스트에 안 들어감
)

# 클래스만으로는 못 가르는 것들 — _is_session_outage()가 내용을 보고 판정한다.
AMBIGUOUS_EXCEPTIONS = (GoogleGenAIAPIError, AnthropicBadRequestError)

FALLBACK_EXCEPTIONS = SESSION_OUTAGE_EXCEPTIONS + REQUEST_SCOPED_EXCEPTIONS + AMBIGUOUS_EXCEPTIONS


def _is_session_outage(exc: BaseException) -> bool:
    """이 실패가 '세션 내내 이 모델을 못 쓴다'는 뜻이면 True, '이번 요청만 실패했다'면 False.

    판별이 애매하면 False(=세션 차단 안 함)로 기운다. 틀렸을 때의 대가가 비대칭이라서다 —
    False로 잘못 보면 최악이 '턴마다 실패 호출 한 번 낭비'인데, True로 잘못 보면 사용자가
    고른 모델이 그 세션 내내 조용히 사라진다(UI에 아무 표시도 없다). 저장소 원칙
    '조용히 자르지 말고 정직하게 실패'와도 방향이 같다."""
    if isinstance(exc, SESSION_OUTAGE_EXCEPTIONS):
        return True
    if isinstance(exc, GoogleGenAIAPIError):
        # google-genai SDK는 4xx/5xx를 한 부모(APIError) 아래 두므로 HTTP 코드로 가른다.
        # 429(쿼터)·403(권한/결제)만 지속이고, 503 과부하는 몇 초 뒤 풀리는 일시 장애라
        # 세션 차단하면 한 번의 blip으로 그 세션 내내 gemini를 못 쓰게 된다.
        return getattr(exc, "code", None) in (403, 429)
    if isinstance(exc, AnthropicBadRequestError):
        # anthropic은 크레딧 부족도 400으로 준다(docs/README_13.md §4 — 실제로 겪은 이중
        # 장애). 잘못된 요청과 예외 클래스가 같아 메시지로만 구분된다. 문구가 바뀌면
        # False로 떨어지는데, 그게 위 docstring이 말한 안전한 쪽이다.
        return "credit balance" in str(exc).lower()
    return False


def _all_failed_error(attempted: list[str], errors: dict[str, str]) -> RuntimeError:
    """모든 후보가 실패했을 때의 예외. 모델별 실패 사유를 메시지에 담는 이유는, 예전엔
    'tried [...] but all failed'만 남아서 **진짜 원인이 통째로 사라졌기** 때문이다 —
    요청 형식이 잘못돼 전 모델이 같은 이유로 실패한 경우와 정말 전 모델이 죽은 경우가
    호출부에서 구분이 안 됐다."""
    detail = "; ".join(f"{m}: {errors[m]}" for m in attempted if m in errors)
    return RuntimeError(f"tried {attempted} but all failed — {detail or '시도할 수 있는 모델이 없음'}")


# 지정된 모델을 우선 호출하고, rate limit 등 발생 시 다른 모델로 자동 전환해 재시도.
def invoke_with_fallback(model,
                         messages,
                         tools: list | None=None,
                         structured=None,
                         models_skip: list[str] | None=None, #임의로 일시정지한 모델
                         disabled_models: list[str] | None=None, #사용량 제한 등으로 세션 내에서 사용 중지할 모델
                         _attempted: list[str] | None=None,  # 재귀 내부용 — 아래 주석 참고
                         _errors: dict[str, str] | None=None):
    if models_skip is None:
        models_skip=[]
    if disabled_models is None:
        disabled_models=[]

    disabled_models = list(disabled_models)   # 방어적 복사 — 호출자의 원본은 절대 건드리지 않는 경계

    # _attempted는 "이번 호출에서 이미 시도해봤다"이고 disabled_models는 "이 세션 내내
    # 못 쓴다"다. 예전엔 disabled_models 하나가 두 역할을 겸했다 — 실패한 모델을 무조건
    # 거기 넣어야만 재귀가 그 모델을 건너뛰었기 때문이다. 그래서 "요청 한정 실패는 세션
    # 차단 안 함"을 구현하려면 둘을 분리하는 게 먼저였다(안 그러면 같은 모델 무한 재시도).
    # 언더스코어를 붙인 건 호출부가 넘길 인자가 아니라 재귀가 스스로 잇는 값이라는 표시.
    attempted = list(_attempted) if _attempted else []
    errors = dict(_errors) if _errors else {}

    temp_models_skip= models_skip+disabled_models+attempted


    primary_name = model
    secondary_name = next((i for i in iter(model_map.keys()) if primary_name!=i and i not in temp_models_skip),None) #다음 모델 없는데?
    primary = model_map[primary_name]()  # 팩토리 함수 호출 — 매번 최신 저장된 키로 새 클라이언트를 만든다

    if primary_name in temp_models_skip:
        if secondary_name is None:  #다 돌아서 없어!
            raise _all_failed_error(attempted, errors)
        else:
            return invoke_with_fallback(secondary_name, messages, tools=tools, structured=structured,
                                        models_skip=models_skip, disabled_models=disabled_models,
                                        _attempted=attempted, _errors=errors)

    if tools:  # tool 객체 리스트(disabled 제외 목록)
        primary = primary.bind_tools(tools)

    if structured:
        # include_raw=True가 없으면 파싱된 스키마 객체만 돌아와서 usage_metadata(토큰 수)에
        # 접근할 방법이 없어짐 — raw(AIMessage)도 같이 받아서 토큰만 뽑아내고, 호출부에는
        # 기존처럼 파싱된 객체만 넘겨 구조 변경이 새지 않게 한다 (generated_by와 같은 패턴)
        primary = primary.with_structured_output(structured, include_raw=True)

    try:
        print(f"LLM 모델 사용: {primary_name}")
        result = primary.invoke(messages)
        if structured:
            response = result["parsed"]
            tokens_used = result["raw"].usage_metadata
        else:
            response = result
            tokens_used = result.usage_metadata
        return response, primary_name, disabled_models, tokens_used
    except FALLBACK_EXCEPTIONS as exc:
        # GoogleGenAIAPIError/AnthropicBadRequestError: langchain_google_genai가 내부적으로
        # google-genai SDK로 갈아탄 뒤로 gemini 과부하(503)가 이 SDK의 원본 예외로 그대로
        # 올라오고, anthropic 크레딧 부족도 openai.BadRequestError와 이름만 같은 별개
        # 클래스로 온다 — 둘 다 실제로 fallback 없이 500까지 새는 걸 겪고 추가함.
        exc_type, exc_value, _ = sys.exc_info()
        error_msg = traceback.format_exception_only(exc_type, exc_value)[0].strip()
        print(error_msg)

        attempted.append(primary_name)
        errors[primary_name] = error_msg

        # 여기가 08-05에 바뀐 지점 — 예전엔 조건 없이 disabled_models.append()였다.
        if _is_session_outage(exc):
            disabled_models.append(primary_name)
            print(f"모델 장애! '{primary_name}' 세션 내 사용 중지 → fallback인 {secondary_name} 모델로 전환")
        else:
            # 이번 요청만 실패한 것이라 세션 차단 목록은 안 건드린다. 다음 턴엔 사용자가
            # 고른 모델을 정상적으로 다시 시도한다.
            print(f"이번 요청 실패(세션 차단 안 함) → fallback인 {secondary_name} 모델로 전환")

        if secondary_name is None:    #다 돌아서 없어!
            raise _all_failed_error(attempted, errors) from exc
        return invoke_with_fallback(secondary_name, messages, tools=tools, structured=structured,
                                    models_skip=models_skip, disabled_models=disabled_models,
                                    _attempted=attempted, _errors=errors)
