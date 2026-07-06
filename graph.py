from dotenv import load_dotenv
#from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_anthropic import ChatAnthropic
from langchain_chroma import Chroma

from langgraph.graph import StateGraph, START, END  

from typing_extensions import TypedDict
from langchain_core.documents import Document

from pydantic import BaseModel, Field
from typing import Literal

from langchain_community.tools import DuckDuckGoSearchRun
#import wikipedia
#wikipedia.set_user_agent("KTB4-jimmy-AI-feynman-agent/0.1 (student project)")
#from langchain_community.tools import WikipediaQueryRun  #user_agent 설정해도 JSONDecodeError 재현됨 (search는 성공하지만 무관한 결과 반환 + 특정 페이지 fetch에서 크래시) — wikipedia 패키지 자체가 신뢰 못 할 수준. wikipedia-api 기반 커스텀 tool 필요 (나중에)
#from langchain_community.utilities import WikipediaAPIWrapper
#from langchain_community.tools.arxiv.tool import ArxivQueryRun
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_core.tools import StructuredTool

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage

from google.api_core.exceptions import ResourceExhausted
from anthropic import RateLimitError
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError


# =========================================================
# Self-RAG 스타일 에이전틱 RAG 그래프
#   retrieve(검색) -> generate(답변 생성, 필요시 tool 호출) -> verify(자체 검증)
#   -> route_by_fix 분기: 문제없거나 limit 도달 시 종료 /
#      컨텍스트 부족하면 retrieve로 / 아니면 generate로 돌아가 재시도
# =========================================================


from typing import NamedTuple

class SiteConfig(NamedTuple): # 수정 불가능하게+3개 변수 딕셔너리에
    domain: str
    description: str

ddg_sites_map = {
    "wikipedia": SiteConfig("en.wikipedia.org", "위키피디아에서 검색"),
    "arxiv": SiteConfig("arxiv.org", "arXiv 논문 검색"),
}
# 팩토리 — 딱 한 번만 정의
def make_search_tool(name: str, config: SiteConfig):
    def search(query: str) -> str:
        return DuckDuckGoSearchAPIWrapper().run(f"site:{config.domain} {query}")
    return StructuredTool.from_function(
        func=search,
        name=f"search_{name}",
        description=config.description,
    )
# .items()로 name과 config를 같이 꺼냄
site_tools = [make_search_tool(name, config) for name, config in ddg_sites_map.items()]

#bind tools
tools = [DuckDuckGoSearchRun(description="일반 범용성 검색"),
        #WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper()), #user_agent 설정해도 JSONDecodeError — wikipedia 패키지 자체 신뢰성 문제, 커스텀 tool 필요
        #ArxivQueryRun(),  #arxiv.org 서버 자체 이슈 (2025-11 이후), langchain_community도 구버전 API 요구
        *site_tools
        ]
tool_map = {tool.name: tool for tool in tools} #이름으로 검색할 수 있게


#api key 가져오기
load_dotenv()

#모델 선택 기능을 위한 map 
model_map = {
    "gemini": ChatGoogleGenerativeAI(model="gemini-2.5-flash"),
    "claude": ChatAnthropic(model="claude-haiku-4-5-20251001")
    }


    
#chromadb 불러오기
# 로컬 임베딩 모델 사용 (BAAI/bge-m3, 다국어) — ingest.py와 반드시 같은 모델이어야 함
# (모델이 다르면 벡터 공간이 달라져서 유사도 검색이 무의미해짐)
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-m3") # 이건 모델 선택 불가-이미 임베딩함
vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=embeddings,
    collection_name="feynman"
)

#LangGraph State 구성 - 그래프 전체 노드가 공유하는 상태
class State(TypedDict):
    question: str
    context: list[Document]
    answer: str
    fix_needed: bool #False
    what_to_fix: str 
    needs_more_context: bool #False
    top_k: int #3
    try_count: int #0
    limit: int #4
    #arxiv_references: list[str]
    model: str #"gemini" or "claude"

# 에러나면 서브 모델로
# state["model"]로 지정된 모델을 우선 호출하고, ResourceExhausted(rate limit) 발생 시
# 다른 모델로 자동 전환해서 재시도
def invoke_with_fallback(model, messages, use_tools=False, structured=None, sub_model=False, models_tried=None):
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
            return invoke_with_fallback(secondary_name, messages, use_tools=use_tools, structured=structured, sub_model=False, models_tried=models_tried)

    if use_tools:
        primary = primary.bind_tools(tools)
    
    if structured:
        primary = primary.with_structured_output(structured)
    
    try:
        print(f"LLM 모델 사용: {primary_name}")
        return primary.invoke(messages)
    except (ResourceExhausted, RateLimitError, ChatGoogleGenerativeAIError):
        print(f"모델 오류! fallback인 {secondary_name} 모델로 전환")
        models_tried.append(primary_name)
        return invoke_with_fallback(secondary_name, messages, use_tools=use_tools, structured=structured, sub_model=False, models_tried=models_tried)


    
# needs_more_context가 True면(verify 단계에서 컨텍스트 부족 판단) top_k를 늘려 재검색
def retrieve(state: State) -> dict:
    if state.get('try_count',0)==0:
        print(f"질문: {state['question']}") 
    k = state.get("top_k", 3) + (1 if state.get("needs_more_context") else 0)
    docs = vectorstore.as_retriever(search_kwargs={"k": k}).invoke(state["question"])
    return {"context": docs, "needs_more_context": False, "top_k": k}

# 문서 기반으로 답변 생성. 모델이 tool 호출을 요청하면 결과를 메시지에 추가해
# 다시 호출하는 ReAct 스타일 루프를 최대 3라운드까지 돈다
def generate(state: State) -> dict:
    print("---"+str(state.get("try_count", 0)+1)+"번째 시도---")

    messages = [
        SystemMessage(content=f"""
            다음 문서를 참고해서 답해줘. 문서에 없는 내용은 검색 tool을 사용해.
            문서: {state['context']}
            {f"고칠 부분: {state['what_to_fix']}" if state.get('fix_needed') else ''}
        """),
        HumanMessage(content=state["question"])
    ]
    
    # 같은 tool_response가 두 역할을 함. 처음엔 무슨 툴 쓸까? 최종에는 툴을 사용해서 얻은것(messages에 저장)과 종합한 답변
    # 무슨 tool 쓸까?
    tool_response = invoke_with_fallback(state.get("model", "gemini"), messages, True)

    max_tool_rounds = 3
    tool_rounds = 0
    tool_docs=[]
    # tool을 쓰는 동안 루프 - tool 쓸 거 없으면 탈출
    while tool_response.tool_calls and tool_rounds < max_tool_rounds:

        # 요청된 tool들을 실제 실행
        tool_results = [
            tool_map[tc["name"]].invoke(tc["args"])
            for tc in tool_response.tool_calls # 무슨 툴 쓸지 정한 거에서
        ]
        print("사용한 도구들")
        print(list(zip([tc["name"] for tc in tool_response.tool_calls],tool_results)))

        # tool 호출 메시지 + 결과(ToolMessage)를 대화 기록에 추가하고 다시 모델 호출
        messages += [
            tool_response,
            *[ToolMessage(content=v, tool_call_id=tc["id"])
            for tc, v in zip(tool_response.tool_calls, tool_results)]
        ]

        tool_docs+= [Document(page_content=str(v), metadata={"source": tc["name"]}) 
                     for tc, v in zip(tool_response.tool_calls, tool_results)]
        
        #다시, 무슨 tool 쓸까?
        tool_response = invoke_with_fallback(state.get("model", "gemini"), messages, True)
        
        tool_rounds += 1

    #tool_response.context는 str이거나, list[dict]이거나, text attribute를 가진 list[object]일 수 있음
    answer = tool_response.content if isinstance(tool_response.content, str) else "".join(
        block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
        for block in tool_response.content
    )    
    print("답변")
    print(answer)
    
    return {"answer" : answer, "fix_needed" : False, "context": state["context"]+tool_docs}


# verify 단계에서 모델이 이 스키마 형태(structured output)로 답변을 채워서 반환
class verified(BaseModel):
    fix_needed: bool = Field(description="answer가 수정이 필요한지 여부")
    what_to_fix: str = Field(description="고쳐야 하는 부분들")
    needs_more_context: bool = Field(description="수정할 때 추가 정보가 필요한지 여부")

# self-RAG 스타일 자체 검증: 문서+모델 지식으로 answer가 맞는지 판단하고
# 수정 필요 여부/이유/추가 컨텍스트 필요 여부를 structured output으로 받는다
def verify(state: State) ->dict:
    print("---verify 단계 시작---")

    messages = [
    SystemMessage(content=f"""
        다음 문서와 네가 알고 있는 지식을 종합해서 답이 맞는지 확인해줘.
        문서에 근거가 없더라도 네 지식으로 판단해도 돼.
        문서: {state["context"]}
    """),
    HumanMessage(content=state["question"]),
    AIMessage(content=state["answer"])
    ]

    answer = invoke_with_fallback(state.get("model", "gemini"), messages, structured=verified, sub_model=True)
   
    print("수정 필요한가: "+str(answer.fix_needed))
    print("고칠점: "+str(answer.what_to_fix))


    return {"fix_needed" : answer.fix_needed, 
            "what_to_fix" : answer.what_to_fix, 
            "try_count" : state.get("try_count", 0)+1,
            "needs_more_context" : answer.needs_more_context
            }


# verify 결과로 다음 노드를 정하는 조건부 엣지 함수
# 수정 불필요 or 시도 횟수 limit 도달 -> 종료
# 수정 필요 + 컨텍스트 부족 -> retrieve(재검색)
# 수정 필요 + 컨텍스트는 충분 -> generate(재생성)
def route_by_fix(state: State) -> Literal["final_answer", "retrieve","generate"]:
    if not state["fix_needed"] or state["try_count"] >= state.get("limit",4):
        return "final_answer"

    elif state["needs_more_context"]:
        return "retrieve"

    else:
        return "generate"

# 그래프의 종료 노드. limit에 걸려 강제 종료된 경우 실패 사유를 답변에 덧붙인다
def final_answer(state: State) ->dict:
    print("-----최종답변-----")
    if state["fix_needed"]:
        answer_f=f"limit:{state['try_count']} 내에 적합한 답변 도출 불가능 \n {state['answer']} \n 발견된 문제점: {state['what_to_fix']}"
        print("최종답변: "+answer_f)
        return {"answer" : answer_f}

    else:
        print("최종답변: "+state["answer"])
        return {"answer": state["answer"]}

      
# === 그래프 빌더 생성 === <-langchain의 chain과 동격
graph = StateGraph(State) # 상태 스키마를 기반으로 그래프 빌더 생성

# === 노드 등록 ===
graph.add_node("retrieve", retrieve) # 이름, 함수
graph.add_node("generate", generate)
graph.add_node("verify", verify)
graph.add_node("final_answer", final_answer)


# === 엣지 연결 ===
graph.add_edge(START, "retrieve")
graph.add_edge("retrieve", "generate") 
graph.add_edge("generate", "verify") 
graph.add_conditional_edges(
	"verify",
	route_by_fix,
	{
	"generate": "generate",
	"final_answer": "final_answer",
    "retrieve": "retrieve"
	},
)
graph.add_edge("final_answer", END) 


# === 컴파일 ===
app = graph.compile()    # 빌더를 실행 가능한 그래프로 변환

# === 실행 ===
#end_answer = app.invoke({"question": "파인만이 설명한 강력이 뭐야?"})["answer"]
#print(end_answer)

# === 시각화용 그래프 구조 객체 가져오기 ===
#graph_view = app.get_graph()

# === 형식 1: Mermaid 텍스트 출력 ===
#mermaid_text = graph_view.draw_mermaid()
#print(mermaid_text)