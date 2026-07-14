#모델 선택 기능을 위한 map
import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from google.api_core.exceptions import ResourceExhausted
from anthropic import RateLimitError
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from openai import APIConnectionError  # 로컬 llama-server가 꺼져 있을 때 나는 접속 에러
from openai import BadRequestError 

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
        api_key="not-needed",  # 로컬 서버는 키 검사 안 함 (필드가 필수라 더미값)
        max_tokens=10000,
        frequency_penalty=0.3,
        model=os.getenv("LOCAL_MODEL_NAME", "qwen-tuned"),
    ),
    }

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
        primary = primary.with_structured_output(structured)
    
    try:
        print(f"LLM 모델 사용: {primary_name}")
        return primary.invoke(messages), primary_name, disabled_models
    except (ResourceExhausted, RateLimitError, ChatGoogleGenerativeAIError, APIConnectionError, BadRequestError):
        exc_type, exc_value, _ = sys.exc_info()
        error_msg = traceback.format_exception_only(exc_type, exc_value)[0].strip()
        print(error_msg)
        print(f"모델 오류! fallback인 {secondary_name} 모델로 전환")

        disabled_models.append(primary_name)
        if secondary_name is None:    #다 돌아서 없어!                   
            raise RuntimeError(f"tried {temp_models_skip} but all failed")
        return invoke_with_fallback(secondary_name, messages, tools=tools, structured=structured, models_skip=models_skip, disabled_models=disabled_models)
