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
        model=os.getenv("LOCAL_MODEL_NAME", "qwen-tuned"),
    ),
    }

# 에러나면 서브 모델로
# 지정된 모델을 우선 호출하고, ResourceExhausted(rate limit) 발생 시
# 다른 모델로 자동 전환해서 재시도
def invoke_with_fallback(model, messages, tools: list | None=None, structured=None, sub_model=False, models_tried=None):
    if models_tried is None:
        models_tried=[]

    if model is None:    #다 돌아서 없어!                   
        raise RuntimeError(f"tried {models_tried} but all failed")
    
    primary_name = model
    secondary_name = next((i for i in iter(model_map.keys()) if primary_name!=i and i not in models_tried),None)
    primary = model_map[primary_name]

    if sub_model == True or primary_name in models_tried:
        if secondary_name is None:  #다 돌아서 없어!
            raise RuntimeError(f"tried {models_tried} but all failed")
        else:
            return invoke_with_fallback(secondary_name, messages, tools=tools, structured=structured, sub_model=False, models_tried=models_tried)

    if tools:  # tool 객체 리스트(disabled 제외 목록)
        primary = primary.bind_tools(tools)
    
    if structured:
        primary = primary.with_structured_output(structured)
    
    try:
        print(f"LLM 모델 사용: {primary_name}")
        return primary.invoke(messages)
    except (ResourceExhausted, RateLimitError, ChatGoogleGenerativeAIError, APIConnectionError):
        print(f"모델 오류! fallback인 {secondary_name} 모델로 전환")
        models_tried.append(primary_name)
        return invoke_with_fallback(secondary_name, messages, tools=tools, structured=structured, sub_model=False, models_tried=models_tried)
