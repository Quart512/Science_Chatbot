from typing import Annotated, Literal

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer

from graph import app as physics_qa_app, _add_tokens

# =========================================================
# 부모(오케스트레이터) 그래프 — "표면"이 보는 대화 이력·체크포인터를 소유한다.
# 지금은 능력이 물리 QA 하나뿐이라 라우팅 없이 곧장 물리 QA로 감(6-7에서 실제 라우터 추가 예정).
#
# 능력을 부모 노드로 "직접" 꽂지 않고 래퍼 함수에서 invoke()로 입출력을 명시 매핑하는 이유:
#   - 물리 QA의 State(try_count, tool_rounds, disabled_tools 등)는 그 능력 내부 전용이라
#     부모가 알 필요도, State 스키마를 공유할 이유도 없음
#   - messages(add_messages reducer)를 공유하면 능력 내부의 재시도 초안·tool 메시지가
#     그대로 부모 이력에 섞여버림 — 래퍼가 "이번에 새로 추가된 깨끗한 메시지만" 골라 반환
# =========================================================


class ParentState(BaseModel):
    question: str
    answer: str = ""
    comment: str = ""
    model: Literal["gemini", "claude", "Qwen-tuned"] = "gemini"
    # "얼마나 열심히 검색·재시도할지"를 low/medium/high 프로필로 노출 — Claude의 reasoning effort와 같은 패턴.
    # 실제 top_k/limit 숫자로의 매핑은 능력마다 다를 수 있는 내부 지식이라 여기 두지 않고 각 능력(graph.py의
    # EFFORT_PROFILES) 안에 둔다. model과 마찬가지로 "사용자가 매 요청마다 고르는 값"이라 부모가 그대로 통과시킴
    effort: Literal["low", "medium", "high"] = "medium"
    tokens_used: dict = Field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
    disabled_models: list[str] = Field(default_factory=list)  # 모델 서킷 브레이커 — 능력들이 공유(한 능력에서 gemini 고장나면 다른 능력도 회피)
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)


def physics_qa_node(state: ParentState) -> dict:
    # get_stream_writer(): 부모(orchestrator)가 stream_mode="custom"으로 스트리밍될 때만 실제로
    # 뭔가를 흘려보내는 "쓰기 채널". 일반 invoke()/stream_mode 미사용 호출에서는 그냥 아무 효과 없는
    # no-op이라 안전 — 그래서 아래 로직이 기존 동기 호출(테스트 등)을 전혀 깨지 않는다.
    writer = get_stream_writer()

    # 능력을 fresh invoke()하는 대신 stream(stream_mode="values")으로 돌린다 — "values"는 매 노드가
    # 끝날 때마다 그 시점까지의 전체 State를 스냅샷으로 주므로, 마지막 스냅샷은 기존 invoke()의
    # 반환값과 완전히 동일하다(정확성 그대로 유지). 그 대신 중간 스냅샷들을 이용해 진행 상황을
    # writer로 부모 스트림에 흘려보낼 수 있다 — trace는 각 노드가 계속 이어붙이는 내부 디버그 로그라
    # 매번 그 시점 전체를 보내면 "지금까지의 판단 기록"이 그대로 진행 로그가 된다. (comment는 이거랑
    # 다른 채널 — verify/final_answer가 채우는 "진짜 사용자용 코멘트"라 진행 중엔 안 보내고 최종에만 실어 보냄)
    result = None
    for snapshot in physics_qa_app.stream({
        "question": state.question,
        "messages": state.messages,          # 지금까지의 대화 이력을 그대로 넘김 (능력 내부에서 단기기억으로 씀)
        "model": state.model,
        "effort": state.effort,              # low/medium/high 그대로 전달 — 숫자 매핑은 능력 내부(graph.py) 책임
        "disabled_models": state.disabled_models,
        "turn_start_len": len(state.messages),  # 이 길이 이후가 "이번 호출에서 새로 쌓인 것" — 능력이 알아서 정리해 돌려줌
    }, stream_mode="values"):
        result = snapshot
        writer({"trace": result.get("trace", ""), "final": False})

    # 스트림이 끝났다는 건 final_answer까지 완료됐다는 뜻 — 이번엔 answer+comment(사용자용)까지 실어
    # "최종 답변 도착"을 final=True로 신호. trace도 마지막 한 번 더 실어서 "판단 과정 보기"가 전체를 볼 수 있게
    writer({"trace": result.get("trace", ""), "answer": result["answer"], "comment": result["comment"], "final": True})

    # 능력이 돌려준 messages는 [기존 이력 그대로] + [이번 턴 정리된 질문+최종답변]이므로,
    # 뒷부분(새로 생긴 것)만 잘라내 부모의 add_messages reducer에 넘긴다 — add_messages는 id 기준
    # 병합이라 통째로 넘겨도 "중복 append"는 안 되지만(기존 id는 교체될 뿐), 매 턴 안 바뀐 옛
    # 메시지들까지 매번 교체 시도(내용은 같아 눈에 안 보이는 낭비)하게 되므로 아예 슬라이싱으로 피한다
    new_msgs = result["messages"][len(state.messages):]

    return {
        "answer": result["answer"],
        "comment": result["comment"],
        "tokens_used": _add_tokens(state.tokens_used, result["tokens_used"]),
        "disabled_models": result["disabled_models"],
        "messages": new_msgs,
    }


graph = StateGraph(ParentState)
graph.add_node("physics_qa", physics_qa_node)
graph.add_edge(START, "physics_qa")
graph.add_edge("physics_qa", END)

# 단기기억(멀티턴)·체크포인터는 여기(부모)가 소유 — 개별 능력은 더 이상 자기 checkpointer를 갖지 않는다
memory = MemorySaver()
app = graph.compile(checkpointer=memory)

if __name__ == "__main__":
    result = app.invoke(
        {"question": "파인만이 설명한 강력이 뭐야?"},
        config={"configurable": {"thread_id": "test"}},
    )
    print(result["answer"])
