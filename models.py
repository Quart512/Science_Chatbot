#모델 선택 기능을 위한 map
import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from google.api_core.exceptions import ResourceExhausted, PermissionDenied  # PermissionDenied: 결제 계정 정지 등으로 403 뜰 때
from anthropic import RateLimitError
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from openai import APIConnectionError  # 로컬 llama-server가 꺼져 있을 때 나는 접속 에러
from openai import BadRequestError 
from openai import LengthFinishReasonError

import sys
import traceback
#api key 가져오기
load_dotenv()

model_map = {
    "gemini": ChatGoogleGenerativeAI(model="gemini-2.5-flash"),
    "claude": ChatAnthropic(model="claude-haiku-4-5-20251001"),
    # 파인튜닝한 Qwen2.5-1.5B (Q4_K_M GGUF)를 로컬 llama-server(OpenAI 호환)로 서빙.
    # 클라이언트 생성은 접속이 아니므로 서버가 꺼져 있어도 이 dict는 안전 — 접속은 invoke 때 일어남.
    # 서버 실행: llama-server -m models/qwen_finetuned_Q4_K_M.gguf --port 8080
    "Qwen-tuned": ChatOpenAI(
        base_url=os.getenv("LOCAL_MODEL_URL", "http://localhost:8080/v1"), 
        # LOCAL_MODEL_URL이 docker-compose.yml로부터 주어진다면(로컬 터미널이 아니라 docker 컨테이너로 열었다면) 
        # localhost:8080이 아니라 llama-server:8080 사용하고,
        # 그 docker compose가 만든 내부 네트워크의 내장 DNS 기능으로 llama-server:8080을 
        api_key="not-needed",  # 로컬 서버는 키 검사 안 함 (필드가 필수라 더미값)
        max_tokens=10000,
        frequency_penalty=0.3,
        model=os.getenv("LOCAL_MODEL_NAME", "qwen-tuned"),
    ),
    }

# =========================================================
# 모델별 컨텍스트 예산 (문자 수 기준) — 논문 분석기(②a)가 LLM을 호출하기 "전에"
# 입력 길이를 미리 체크할 때 쓴다. 토큰이 아니라 문자 수인 이유: 이 프로젝트의
# 다른 길이 기준(ingest.py 청크 500자, paper_sections.py의 max_chars)도 전부
# 문자 수 기준이라 통일 — 프로바이더별 토크나이저까지 정확히 계산할 만큼의
# 정밀도가 필요한 지점이 아니라, 안전 마진을 넉넉히 둔 대략치로 충분하다.
#
# gemini-2.5-flash/claude-haiku는 실질 컨텍스트가 커서(각각 100만/20만 토큰급)
# 논문 한 편 분량으로는 거의 걸리지 않는다 — 그래서 넉넉하게 잡아둠.
# Qwen-tuned(로컬 llama-server)가 실제로 걸릴 수 있는 쪽이다 — llama-server
# 기동 커맨드에 --ctx-size를 명시하지 않아 기본값(4096 토큰)을 그대로 쓰고
# 있고, 한국어는 토큰당 문자 수가 더 적게 들어가는 경향이 있어 보수적으로
# 잡았다. **아직 실측하지 않은 대략치 — 실제로 예산 초과가 관찰되면 여기
# 숫자를 조정한다** (모델 정책의 단일 지점을 유지하기 위해 이 dict 하나만
# 고치면 되도록).
CONTEXT_BUDGET_CHARS: dict[str, int] = {
    "gemini": 800_000,
    "claude": 150_000,
    "Qwen-tuned": 6_000,
}


class ContextBudgetExceeded(Exception):
    """모델별 컨텍스트 예산을 넘었을 때 발생시키는 예외.

    invoke_with_fallback()의 except 목록(ResourceExhausted 등)에는 없다 —
    일부러 그렇게 뒀다. 저 목록에 넣으면 "컨텍스트가 너무 길어서 실패"한 걸
    "이 모델이 고장났다"로 오인해 다음 모델로 fallback해버리는데, 다음 모델도
    똑같이 길이 때문에 실패할 뿐이라 문제가 해결되지 않는다(models.py를
    "model_map+fallback 정책의 단일 지점"으로 유지한다는 원칙과도 별개 —
    여긴 fallback이 아니라 애초에 부르지 않는 게 맞는 상황이다).
    이 함수는 실제 모델 API를 호출하기 "전에" 체크하므로, 이 예외가 나면
    비용은 0이다.
    """

    def __init__(self, model: str, text_len: int, budget: int):
        self.model = model
        self.text_len = text_len
        self.budget = budget
        super().__init__(
            f"'{model}' 컨텍스트 예산({budget:,}자) 초과 — 입력 길이 {text_len:,}자. "
            "분할(map-reduce)은 아직 미구현 — 조용히 자르지 않고 정직하게 실패."
        )


def check_context_budget(model: str, text: str) -> None:
    """model로 text를 보내기 전에 길이가 예산 안에 드는지 확인한다.

    예산을 넘으면 ContextBudgetExceeded를 raise — 호출한 쪽(논문 분석기 등)이
    이걸 잡아서 "논문이 길어 요약 불가(분할 미구현)" 같은 정직한 실패 메시지를
    사용자에게 전달하는 데 쓴다. CONTEXT_BUDGET_CHARS에 없는 model 이름이면
    예산 자체가 없는 것으로 보고 통과시킨다.
    """
    budget = CONTEXT_BUDGET_CHARS.get(model)
    if budget is not None and len(text) > budget:
        raise ContextBudgetExceeded(model, len(text), budget)


# 에러나면 서브 모델로
# 지정된 모델을 우선 호출하고, ResourceExhausted(rate limit) 발생 시
# 다른 모델로 자동 전환해서 재시도
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
    primary = model_map[primary_name]

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
            BadRequestError, LengthFinishReasonError):
        exc_type, exc_value, _ = sys.exc_info()
        error_msg = traceback.format_exception_only(exc_type, exc_value)[0].strip()
        print(error_msg)
        print(f"모델 오류! fallback인 {secondary_name} 모델로 전환")

        disabled_models.append(primary_name)
        if secondary_name is None:    #다 돌아서 없어!                   
            raise RuntimeError(f"tried {temp_models_skip} but all failed")
        return invoke_with_fallback(secondary_name, messages, tools=tools, structured=structured, models_skip=models_skip, disabled_models=disabled_models)
