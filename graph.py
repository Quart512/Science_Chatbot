#from langchain_text_splitters import RecursiveCharacterTextSplitter

from langgraph.graph import StateGraph, START, END  

from langchain_core.documents import Document

from pydantic import BaseModel, Field
from typing import Literal, Annotated
from langgraph.graph.message import add_messages

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage, BaseMessage, RemoveMessage

from models import invoke_with_fallback
from tool import tools_list, tool_map
from retrieval import vectorstore

from langgraph.checkpoint.memory import MemorySaver

# =========================================================
# Self-RAG 스타일 에이전틱 RAG 그래프
#   retrieve(검색) -> generate(답변 생성) -(tool_calls 있으면)-> tools(실행) -> generate 루프
#   -(없으면)-> verify(자체 검증) -> route_by_fix 분기:
#      문제없거나 limit 도달 시 종료 / 컨텍스트 부족하면 retrieve로 / 아니면 generate 재시도
#   tool 예외처리: 실패도 반드시 ToolMessage로 응답(API 요구사항) -> LLM이 다음 라운드에
#   에러를 읽고 자가수정. 연속 2회 실패한 tool은 disabled_tools로 이번 런에서 제외(서킷 브레이커)
# =========================================================


# 여러 노드에 걸쳐 tokens_used를 계속 더해 넣을 때 쓰는 헬퍼.
# current(state.tokens_used)는 Pydantic default_factory가 키를 보장해주지만,
# new(LLM provider가 반환한 usage_metadata)는 우리가 통제 못 하는 외부 값이라
# 키가 다르거나 없을 수 있음 — 그래서 new 쪽을 위해 .get(...,0)으로 방어.
# 합집합이 아니라 이 세 스칼라 키만 골라서 더한다 — provider별로 딸려오는
# input_token_details(dict) 같은 중첩 세부 항목까지 합치려 하면 int+dict로 터짐
TOKEN_KEYS = ("input_tokens", "output_tokens", "total_tokens")

def _add_tokens(current: dict, new: dict) -> dict:
    return {k: current.get(k, 0) + new.get(k, 0) for k in TOKEN_KEYS}


#LangGraph State 구성 - 그래프 전체 노드가 공유하는 상태
class State(BaseModel):
    question: str
    context: list[Document] = Field(default_factory=list)
    answer: str = Field(default="")
    comment: str = ""
    tokens_used: dict = Field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
    fix_needed: bool = False
    what_to_fix: str = ""
    needs_more_context: bool = False
    top_k: int = 3
    try_count: int = 0
    limit: int = 4
    #arxiv_references: list[str]
    model: Literal["gemini", "claude", "Qwen-tuned"] = "gemini"
    generated_by: str = ""
    disabled_models: list[str] = Field(default_factory=list)
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)  # 대화 이력 (reducer가 자동 누적 — 노드는 새 메시지만 반환)
    tool_rounds: int = 0 # 이번 답변 시도에서 tools 노드를 돈 횟수
    tool_failures: dict[str,int] = Field(default_factory=dict) # tool별 연속 실패 횟수
    disabled_tools: list[str] = Field(default_factory=list) # 서킷 브레이커로 제외된 tool 이름들. tool_failures로 tool 쓸 때마다 갯수 체크해서 일정 갯수 이하만 할수도 있는데 커스텀으로 툴 제외하는 옵션 위해
    turn_start_len: int = 0 # 이번 턴 시작 시점의 messages 길이. final_answer에서 "이번 턴에 쌓인 메시지"(재시도 초안, tool 호출/응답 등) 경계로 씀 — 이 이후 것만 지우고 질문+최종답변으로 정리

#멀티턴 대비 초기화(messages 제외)
def reset_turn(state: State) -> dict:
    return{
        "context": [],
        "answer": "",
        "comment": "",
        "tokens_used": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "fix_needed": False,
        "what_to_fix": "",
        "needs_more_context": False,
        "try_count": 0,
        "generated_by": "",
        "disabled_models": [],
        "tool_rounds": 0, # 이번 답변 시도에서 tools 노드를 돈 횟수
        "tool_failures": {}, # tool별 연속 실패 횟수
        "disabled_tools":[], # 서킷 브레이커로 제외된 tool 이름들. tool_failures로 tool 쓸 때마다 갯수 체크해서 일정 갯수 이하만 할수도 있는데 커스텀으로 툴 제외하는 옵션 위해
        "turn_start_len": len(state.messages) # 지금 시점 = 이번 턴 이전까지의 메시지 개수. final_answer가 이걸 경계로 이번 턴 메시지만 정리
        }

# needs_more_context가 True면(verify 단계에서 컨텍스트 부족 판단) top_k를 늘려 재검색
def retrieve(state: State) -> dict:
    if state.try_count==0:
        print(f"질문: {state.question}")
    k = state.top_k + (1 if state.needs_more_context else 0)
    docs = vectorstore.as_retriever(search_kwargs={"k": k}).invoke(state.question)
    # 재검색 시 벡터DB 문서는 새것으로 교체하되(단순 합치면 겹치는 문서가 중복 누적),
    # tool로 수집한 증거는 보존 — tool 문서는 metadata source가 tool 이름 (chroma 문서는 "feynman")
    tool_docs = [d for d in state.context if d.metadata.get("source") in tool_map]
    return {"context": docs + tool_docs, "needs_more_context": False, "top_k": k}

# 문서 기반으로 답변 생성. tool 실행은 별도 tools 노드가 담당 (ReAct 루프를 그래프 구조로).
# system prompt는 state에 안 쌓고 매번 최신 context로 새로 조립 — messages에는 Human/AI/Tool만 쌓인다

def generate(state: State) -> dict:
    print("---"+str(state.try_count+1)+"번째 시도---")

    system = SystemMessage(content=f"""
        너는 물리학 지식을 갖춘 어시스턴트다. 질문에는 네가 이미 알고 있는 지식을 우선으로 답해라.
        아래 문서와 tool 결과는 참고 자료일 뿐이다 — 네 지식이 확실하면 그대로 답하고,
        문서 내용이 틀렸거나 질문과 무관하면 무시해라. 네 지식만으로 부족하거나
        최신·구체적 사실 확인이 필요할 때만 검색 tool을 사용해라.
        문서가 질문과 아예 무관하지는 않지만 질문의 핵심 쟁점(예: 여러 해석·이론이 경쟁 중인지,
        아직 결론이 나지 않은 문제인지)까지는 다루지 않는다면, 문서에 없는 내용이라도
        네 지식으로 그 핵심 쟁점을 보완해서 답에 반드시 포함시켜라 — 문서가 다루는 인접 주제만
        답하고 정작 질문이 묻는 핵심을 빠뜨리면 안 된다.
        {"(지금은 사용 가능한 검색 tool이 없다. 네 지식만으로 답해.)" if len(state.disabled_tools) >= len(tool_map) else ""}

        참고 문서: {state.context}
    """)

    history = state.messages  # 메세지 불러오기
    new_msgs = []
    if state.try_count==0:  # 첫 진입: 질문을 이력에 등록
        new_msgs.append(HumanMessage(content=state.question))
    if state.fix_needed and state.what_to_fix:  # verify가 되돌린 재시도: 지적사항을 대화로 전달
        new_msgs.append(HumanMessage(content=f"참고: 이전 답변에 대한 검증 의견 — {state.what_to_fix}\n타당하면 반영하고, 아니면 네 판단을 유지해도 된다. 최종 답변만 다시 제시해."))
    # 서킷 브레이커: disabled 제외한 tool만 바인딩
    active_tools = [t for t in tools_list if t.name not in state.disabled_tools]

    # tool 써야 하는지 아닌지 판별해서 tool_calls 요청, 필요 없다고 판단되면 일반 텍스트 답변
    response, generated_by, disabled_models, tokens_used = invoke_with_fallback(state.model,
                                                                [system] + history + new_msgs,
                                                                tools=active_tools,
                                                                disabled_models=state.disabled_models)

    #response.content는 str이거나, list[dict]이거나, text attribute를 가진 list[object]일 수 있음
    answer = response.content if isinstance(response.content, str) else "".join(
        block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
        for block in response.content
    )
    if response.tool_calls:
        print("tool 요청: " + str([tc["name"] for tc in response.tool_calls]))
    else:
        print("답변")
        print(answer)

    # messages는 add_messages reducer가 누적하므로 새 메시지만 반환
    return {"messages": new_msgs + [response], 
            "answer": answer, 
            "fix_needed": False, 
            "generated_by": generated_by,
            "disabled_models": disabled_models,
            "tokens_used": _add_tokens(state.tokens_used, tokens_used),
            "comment" : state.comment+
            f"""------\n{state.try_count+1}번째 generate 결과: {"tool 요청: " + str([tc["name"] for tc in response.tool_calls]) if response.tool_calls else answer}{f"\n {set(disabled_models) - set(state.disabled_models)} 제외됨" if set(disabled_models) - set(state.disabled_models) else ""}"""
            }


# generate가 tool을 요청했으면 tools 노드로, 아니면 verify로
def route_after_generate(state: State) -> Literal["run_tools", "verify"]:
    last = state.messages[-1]
    return "run_tools" if getattr(last, "tool_calls", None) else "verify"


MAX_TOOL_ROUNDS = 3

# tool 실행 노드. 핵심 규칙: 모든 tool_call에는 반드시 대응하는 ToolMessage를 반환해야 한다
# (Gemini·Claude API 공통 — 응답 없는 tool_call이 있으면 다음 invoke가 에러).
# 따라서 실패도 에러 ToolMessage로 답한다 → LLM이 다음 라운드에 읽고 스스로 전략을 바꾼다.
def run_tools(state: State) -> dict:
    last = state.messages[-1]
    failures = dict(state.tool_failures) #각 툴들이 몇번 실패했는지
    disabled = list(state.disabled_tools) #제외된 툴들
    rounds = state.tool_rounds

    tool_msgs, tool_docs = [], []
    for tc in last.tool_calls:
        name, tid = tc["name"], tc["id"]

        # 라운드 한도 초과: 실행하지 않고 "그만 쓰고 답해"로 응답
        if rounds >= MAX_TOOL_ROUNDS:
            tool_msgs.append(ToolMessage(content="[한도 초과] tool 사용 한도에 도달했다. 지금까지의 문서와 정보만으로 답해.",
                                         tool_call_id=tid, status="error"))
            continue
        # LLM이 없는/비활성 tool 이름을 요청한 경우
        if name not in tool_map or name in disabled:
            tool_msgs.append(ToolMessage(content=f"[사용 불가] '{name}'. 사용 가능한 tool: {[n for n in tool_map if n not in disabled]}",
                                         tool_call_id=tid, status="error"))
            continue
        # 실제 실행 — 예외는 인프라 문제
        try:
            result = str(tool_map[name].invoke(tc["args"]))[:4000]  # 길이 제한: messages+context 이중 반입되므로 토큰 폭발 방지
        except Exception as e:
            failures[name] = failures.get(name, 0) + 1
            if failures[name] >= 2 and name not in disabled:  # 서킷 브레이커
                disabled.append(name)
                print(f"tool '{name}' 연속 {failures[name]}회 실패 → 이번 런에서 비활성화")
            tool_msgs.append(ToolMessage(content=f"[호출 실패] {name}: {type(e).__name__}. 다른 tool을 쓰거나 문서만으로 답해.",
                                         tool_call_id=tid, status="error"))
            continue
        # 빈 결과 — tool은 정상, 쿼리 문제
        if not result.strip():
            tool_msgs.append(ToolMessage(content=f"[결과 없음] {name}. 쿼리를 바꿔 재시도하거나 다른 tool을 사용해.",
                                         tool_call_id=tid))
            continue
        # 성공
        failures[name] = 0  # 연속 실패 카운트 리셋
        tool_msgs.append(ToolMessage(content=result, tool_call_id=tid))
        tool_docs.append(Document(page_content=result, metadata={"source": name}))
        
        print(f"tool 사용: {name}{tc['args']} → {result[:80]}...")


    return {"messages": tool_msgs,
            "context": state.context + tool_docs,  # verify가 tool 근거를 보도록 병합
            "tool_failures": failures,
            "disabled_tools": disabled,
            "tool_rounds": rounds + 1,
            "comment" : state.comment+
            f"""------\n {tool_msgs}\n tool 사용: {", ".join(f"{tc['name']}{tc['args']}" for tc in last.tool_calls) if last.tool_calls else ""}"""}


# verify 단계에서 모델이 이 스키마 형태(structured output)로 답변을 채워서 반환
class verified(BaseModel):
    fix_needed: bool = Field(description="answer가 수정이 필요한지 여부. what_to_fix에 뭔가 적었다면 반드시 True여야 한다." \
    "fix_needed는 사실 오류, 질문과 불일치일 때만 True. 문서에 근거가 없어도 내용이 정확하면 False. 문서 연결 제안은 what_to_fix가 아니라 무시하라")
    what_to_fix: str = Field(description="고쳐야 하는 부분들. 문제가 없으면 반드시 빈 문자열로 남겨라 — 사소한 코멘트라도 여기 적으면 fix_needed는 True로 간주된다.")
    needs_more_context: bool = Field(description="수정할 때 추가 정보가 필요한지 여부")
    comment: str = Field(description=  "사용자가 알아야 할 주의점이 있을 때만 적어라(답변의 한계, 확인 권장 사항 등). 검증 과정이나 판정 근거 설명은 적지 마라. 없으면 빈 문자열." )

# self-RAG 스타일 자체 검증: 문서+모델 지식으로 answer가 맞는지 판단하고
# 수정 필요 여부/이유/추가 컨텍스트 필요 여부를 structured output으로 받는다
def verify(state: State) ->dict:
    print("---verify 단계 시작---")

    messages = [
    SystemMessage(content=f"""
        다음 문서와 네가 알고 있는 지식, 그리고 지금까지의 대화 이력을 종합해서 답이 맞는지 확인해줘.
        대화 이력에 등장한 정보(예: 사용자가 밝힌 이름 등 단기기억)는 근거로 인정해도 된다 — 문서에 없다는 이유만으로 틀렸다고 판단하지 마라.
        문서에 근거가 없더라도 네 지식으로 판단해도 돼.
        문서: {state.context}
        fix_needed는 사실 오류, 질문과 불일치일 때만 True. 문서에 근거가 없어도 내용이 정확하면 False. 문서 연결 제안은 what_to_fix가 아니라 무시하라
        질문이 대화 맥락상 답할 수 없을 만큼 불완전하거나 모호하고(예: 요약할 대상이 이 대화에 없음), 답변이 그 점을 지적하며 명확화를 요청했다면 이는 정확한 대응이므로 fix_needed는 False.
    """),
    ] + state.messages + [
    HumanMessage(f"질문: {state.question}\n\n답변: {state.answer}\n\n이 답변을 검증해줘."),
    ]
    try: # generated_by를 이미 써본 모델로 등록, 다른 모델 시도
        answer, verified_by, disabled_models, tokens_used = invoke_with_fallback(state.model, messages, structured=verified,
                                                                    models_skip=[state.generated_by],
                                                                    disabled_models=state.disabled_models)
    except RuntimeError: # 다른 모델도 전부 실패 -> 차순위: 생성자 본인이 검증
        print("다른 모델도 전부 실패 -> 차순위: 생성자 본인이 검증")

        try:
            answer, verified_by, disabled_models, tokens_used = invoke_with_fallback(state.generated_by, messages, structured=verified,
                                                                    disabled_models=state.disabled_models)
        except RuntimeError: # 차순위도 실패->검증 생략
            print("차순위도 실패->검증 생략")
            return {"fix_needed" : False,
            "what_to_fix" : "",
            "try_count" : state.try_count+1,
            "needs_more_context" : False,
            "tool_rounds" : 0,  # 재시도마다 tool 예산 리셋 (기존 while 루프의 시도별 3라운드와 동일한 정책)
            "disabled_models" : state.disabled_models+ [state.generated_by],
            "comment" : state.comment+
            f"""------\n{state.try_count}번째 verify 결과: generated_by 모델을 포함한 모든 모델 실패->검증 생략"""}
        
    # what_to_fix가 채워졌는데 fix_needed=False로 나오는 (특히 작은/파인튜닝 모델에서 관찰된)
    # 필드 간 불일치에 대한 안전망 — false negative(고칠 게 있는데 통과)가 false positive보다 위험
    fix_needed = answer.fix_needed or bool(answer.what_to_fix.strip())

    print("verify에 사용된 모델:", verified_by)
    print("수정 필요한가: "+str(fix_needed))
    print("고칠점: "+str(answer.what_to_fix))

    return {"fix_needed" : fix_needed,
            "what_to_fix" : answer.what_to_fix,
            "try_count" : state.try_count+1,
            "needs_more_context" : answer.needs_more_context,
            "tool_rounds" : 0,  # 재시도마다 tool 예산 리셋 (기존 while 루프의 시도별 3라운드와 동일한 정책)
            "disabled_models" : disabled_models,
            "tokens_used": _add_tokens(state.tokens_used, tokens_used),
            "comment" : state.comment+
            f"""------\n {state.try_count+1}번째 verify 결과: {fix_needed}{f"\n {set(disabled_models) - set(state.disabled_models)} 제외됨" if set(disabled_models) - set(state.disabled_models) else ""}\n {verified_by} 모델로 verify됨\n {answer.comment} """
            }


# verify 결과로 다음 노드를 정하는 조건부 엣지 함수
# 수정 불필요 or 시도 횟수 limit 도달 -> 종료
# 수정 필요 + 컨텍스트 부족 -> retrieve(재검색)
# 수정 필요 + 컨텍스트는 충분 -> generate(재생성)
def route_by_fix(state: State) -> Literal["final_answer", "retrieve","generate"]:
    if not state.fix_needed or state.try_count >= state.limit:
        return "final_answer"

    elif state.needs_more_context:
        return "retrieve"

    else:
        return "generate"

# 그래프의 종료 노드. 답변을 정리하고 limit에 걸려 강제 종료된 경우 실패 사유를 답변에 덧붙인다
class final_answer_structure(BaseModel):
    final_answer: str = Field(description=(
        "질문에 대한 완결된 답변 본문. 사용자가 이것만 읽어도 충분한 최종 결과물이다."
        "초안의 내용을 수정하거나 요약하지 말 것 — 분리만 하라." 
        "판단 과정, 답변에 대한 자기 평가, 이전 답변·수정에 대한 언급, 문서/검색 출처 언급은 "
        "절대 여기 넣지 마라 — 그런 내용은 전부 comment에 적어라."
        "세계의 불확실성(미해결·논쟁)은 본문에, 너 자신의 불확실성(확신 부족·판단 과정)은 comment에"))
    comment: str = Field(default="", description=(
        "답변 본문이 아닌 모든 말을 적는 곳. 예: 확신이 낮은 부분과 그 이유, "
        "검증 지적을 반영했는지/기각했는지와 그 판단, 참고 자료의 한계, 사용자가 알아야 할 주의점. "
        "이 내용은 버려지지 않고 답변과 함께 사용자에게 별도 표시된다. 적을 것이 없으면 빈 문자열."))
    
def final_answer(state: State) ->dict:
    tokens_used = None
    if state.try_count == 1:  #final answer 분리할 필요 없음
        final_text, comment_text = state.answer, state.comment
    else:
        print("-----최종답변-----")

        messages = [
            SystemMessage(content=
                "너는 답변 편집자다. 주어진 초안을 두 부분으로 분리해라: "
                "final_answer는 질문에 대한 완결된 답변 본문, "
                "comment는 본문이 아닌 모든 말(자기 평가, 판단 과정, 수정 이력 언급, 주의사항). "
                "문장을 수정·요약·재작성하지 말고 그대로 옮겨 담기만 해라. 질문에 새로 답하지 마라."),
            HumanMessage(content=f"질문: {state.question}\n\n초안:\n{state.answer}"),
        ]

        try:
            answer, _, _, tokens_used = invoke_with_fallback(state.generated_by, messages, structured=final_answer_structure,
                                                                        disabled_models=state.disabled_models)
            if state.fix_needed:
                answer_f=f"\nlimit:{state.try_count} 내에 적합한 답변 도출 불가능 \n 남은 문제점: {state.what_to_fix} \n limit/top_k 증가나 다른 모델 재시도 권장"
                final_text, comment_text = answer.final_answer, answer.comment+answer_f
            else:
                final_text, comment_text = answer.final_answer, answer.comment
        except RuntimeError:
            final_text, comment_text = state.answer, state.comment

    print("최종답변: " + final_text)

    # 이번 턴에 쌓인 메시지(재시도 초안, tool 호출/응답 등)는 지우고 질문+최종답변만 남겨서
    # 다음 턴 generate/verify가 보는 대화 이력을 가볍게 유지 — turn_start_len이 이번 턴의 시작 경계
    this_turn_msgs = state.messages[state.turn_start_len:]
    prune = [RemoveMessage(id=m.id) for m in this_turn_msgs]
    clean_msgs = [HumanMessage(content=state.question), AIMessage(content=final_text)]

    result = {"answer": final_text, "comment": comment_text, "messages": prune + clean_msgs}
    if tokens_used is not None:
        result["tokens_used"] = _add_tokens(state.tokens_used, tokens_used)
    return result
      
# === 그래프 빌더 생성 === <-langchain의 chain과 동격
graph = StateGraph(State) # 상태 스키마를 기반으로 그래프 빌더 생성

# === 노드 등록 ===
graph.add_node("reset_turn", reset_turn) # 이름, 함수
graph.add_node("retrieve", retrieve)
graph.add_node("generate", generate)
graph.add_node("run_tools", run_tools)
graph.add_node("verify", verify)
graph.add_node("final_answer", final_answer)


# === 엣지 연결 ===
graph.add_edge(START, "reset_turn")
graph.add_edge("reset_turn", "retrieve")
graph.add_edge("retrieve", "generate")
graph.add_conditional_edges(   # generate → tool 요청 있으면 tools, 없으면 verify
	"generate",
	route_after_generate,
	{"run_tools": "run_tools", "verify": "verify"},
)
graph.add_edge("run_tools", "generate")   # tool 결과 들고 generate로 복귀 (ReAct 루프)
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
memory = MemorySaver()
app = graph.compile(checkpointer=memory) # 빌더를 실행 가능한 그래프로 변환

if __name__ == "__main__":
    # === 실행 ===
    end_answer = app.invoke({"question": "파인만이 설명한 강력이 뭐야?"}, config={"configurable": {"thread_id": "test"}})["answer"]
    print(end_answer)

    # === 시각화용 그래프 구조 객체 가져오기 ===
    print("----------")
    graph_view = app.get_graph()

    # === 형식 1: Mermaid 텍스트 출력 ===
    mermaid_text = graph_view.draw_mermaid()
    print(mermaid_text)