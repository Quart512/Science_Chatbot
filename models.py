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


# 지정된 모델을 우선 호출하고, rate limit 등 발생 시 다른 모델로 자동 전환해 재시도.
def invoke_with_fallback(model,
                         messages, 
                         tools: list | None=None, 
                         structured=None, 
                         models_skip: list[str] | None=None, #임의로 일시정지한 모델
                         disabled_models: list[str] | None=None): #사용량 제한 등으로 세션 내에서 사용 중지할 모델
    if models_skip is None:
        models_skip=[]
    if disabled_models is None:
        disabled_models=[]

    disabled_models = list(disabled_models)   # 방어적 복사 — 호출자의 원본은 절대 건드리지 않는 경계

    temp_models_skip= models_skip+disabled_models

    
    primary_name = model
    secondary_name = next((i for i in iter(model_map.keys()) if primary_name!=i and i not in temp_models_skip),None) #다음 모델 없는데?
    primary = model_map[primary_name]()  # 팩토리 함수 호출 — 매번 최신 저장된 키로 새 클라이언트를 만든다

    if primary_name in temp_models_skip:
        if secondary_name is None:  #다 돌아서 없어!
            raise RuntimeError(f"tried {temp_models_skip} but all failed")
        else:
            return invoke_with_fallback(secondary_name, messages, tools=tools, structured=structured, models_skip=models_skip, disabled_models=disabled_models)

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
    except (ResourceExhausted, PermissionDenied, RateLimitError, ChatGoogleGenerativeAIError, APIConnectionError,
            BadRequestError, LengthFinishReasonError, GoogleGenAIAPIError, AnthropicBadRequestError):
        # GoogleGenAIAPIError/AnthropicBadRequestError: langchain_google_genai가 내부적으로
        # google-genai SDK로 갈아탄 뒤로 gemini 과부하(503)가 이 SDK의 원본 예외로 그대로
        # 올라오고, anthropic 크레딧 부족도 openai.BadRequestError와 이름만 같은 별개
        # 클래스로 온다 — 둘 다 실제로 fallback 없이 500까지 새는 걸 겪고 추가함.
        exc_type, exc_value, _ = sys.exc_info()
        error_msg = traceback.format_exception_only(exc_type, exc_value)[0].strip()
        print(error_msg)
        print(f"모델 오류! fallback인 {secondary_name} 모델로 전환")

        disabled_models.append(primary_name)
        if secondary_name is None:    #다 돌아서 없어!                   
            raise RuntimeError(f"tried {temp_models_skip} but all failed")
        return invoke_with_fallback(secondary_name, messages, tools=tools, structured=structured, models_skip=models_skip, disabled_models=disabled_models)
