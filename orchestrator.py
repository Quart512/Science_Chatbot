from typing import Annotated, Literal

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer

from graph import app as physics_qa_app, _add_tokens
from models import invoke_with_fallback

# =========================================================
# 부모(오케스트레이터) 그래프 — "표면"이 보는 대화 이력·체크포인터를 소유한다.
# 지금은 능력이 물리 QA 하나뿐이라 라우팅 없이 곧장 물리 QA로 감(6-7에서 실제 라우터 추가 예정).
#
# 능력을 부모 노드로 "직접" 꽂지 않고 래퍼 함수에서 invoke()로 입출력을 명시 매핑하는 이유:
#   - 물리 QA의 State(try_count, tool_rounds, disabled_tools 등)는 그 능력 내부 전용이라
#     부모가 알 필요도, State 스키마를 공유할 이유도 없음
#   - messages(add_messages reducer)를 공유하면 능력 내부의 재시도 초안·tool 메시지가
#     그대로 부모 이력에 섞여버림 — 래퍼가 "이번에 새로 추가된 깨끗한 메시지만" 골라 반환
#
# [SqliteSaver 영속화, 6-4·07-31] 이 파일은 이제 컴파일된 app이 아니라 컴파일 "전" graph
# 빌더만 export한다 — 체크포인터 연결(컴파일)은 main.py의 FastAPI lifespan에서 한다.
# 이유: AsyncSqliteSaver는 비동기 컨텍스트 매니저로 열어야 하는데(아래 CHECKPOINT_DB_PATH
# 참고), 그 컨텍스트가 살아있는 동안(서버 생명주기)만 유효하다 — 이 모듈을 임포트하는
# 시점(동기)엔 그 컨텍스트를 열 수 없다. 그래서 "무엇으로 컴파일할지"는 main.py가 결정하고,
# 이 파일은 "무엇을 컴파일할지"(그래프 구조)만 책임진다.
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


# 관심사 등록 제안 훅(08-07 턴 종료 후 훅, 07-31) — "물리 QA는 제안만, 실제 작성·확인은
# 관심사 서비스(interest_writer.py)"로 정리된 설계(설계 논의 참고)의 물리 QA 쪽 절반이다.
# physics_qa_node 안이 아니라 별도 노드로 둔 이유: 물리 QA 능력이 "관심사 서비스"라는
# 다른 능력의 존재를 알 필요가 없어야 한다(캡슐화) — 능력 간 제안·연결은 여러 능력을
# 다 아는 부모(오케스트레이터)의 책임이다.
#
# 대화 내용을 관심사 서비스로 그대로 복사해 넘기지 않는다 — thread_id만 안내하면
# interest_writer.py의 draft()가 그 thread_id로 checkpoints.sqlite를 다시 읽어 초안을
# 만든다(대화가 이미 영속화돼 있다는 6-4의 이점을 그대로 활용).
#
# 매 턴 다시 판정하고 반복 제안을 억제하는 로직은 없다(단순 경로부터, 설계 논의에서
# 의도적으로 미룸) — 같은 주제로 대화가 길어지면 매 턴 제안이 반복될 수 있는데, 실사용에서
# 거슬리면 그때 억제 로직을 추가한다. 판정 자체가 실패해도(모델 전부 소진 등) 원래 답변
# 흐름은 막지 않는다 — register_paper()의 arxiv 자동 조회 실패 처리와 같은 패턴.
#
# SSE로는 별도 청크로 흘려보낸다(07-31, 실사용 테스트로 발견한 문제의 수정) — 처음엔
# comment에 이어붙이기만 했는데, physics_qa_node가 이미 writer({"final": True, ...})로
# 답변을 다 흘려보낸 "뒤"에 이 노드가 도니까 comment에 이어붙인 내용이 스트림엔 전혀
# 안 실리고 체크포인트에만 남았다(실제 TestClient로 재현 확인). "final"의 의미를
# "이게 진짜 답변 본문"으로만 쓰고 "스트림이 끝났다"로는 안 쓰기로 하면, 그 뒤에 이
# 노드가 {"suggestion": ...} 청크를 하나 더 흘려보내도 문제없다 — 프론트는 답변을 먼저
# 렌더링하고, 뒤이어 도착하는 suggestion 청크를 후속 말풍선처럼 보여주면 된다(스트림을
# 늦추지 않으면서도 실제로 전달됨).
INTEREST_SUGGESTION_MODEL = "gemini"

INTEREST_SUGGESTION_PROMPT = """대화 이력을 보고 사용자가 관심사로 등록할 만한 주제를 반복해서
다루고 있는지 판정해라. 한 번의 가벼운 질문에는 제안하지 마라 — 여러 번 같은 주제를 묻거나
사용자가 스스로 "관심 있다"·"더 알아보고 싶다"는 뜻을 밝혔을 때만 제안해라."""


class InterestSuggestion(BaseModel):
    should_suggest: bool = Field(
        description="최근 대화를 보고 사용자가 반복적으로 관심 두는 주제가 있어 "
        "관심사로 등록해볼 만하면 True, 아니면 False"
    )


def suggest_interest_node(state: ParentState, config: RunnableConfig) -> dict:
    if not state.messages:
        return {}

    try:
        messages = [SystemMessage(content=INTEREST_SUGGESTION_PROMPT)] + state.messages
        result, _, _, tokens_used = invoke_with_fallback(
            INTEREST_SUGGESTION_MODEL, messages, structured=InterestSuggestion
        )
    except RuntimeError as e:
        # 판정 자체가 실패해도 이번 턴의 실제 답변은 이미 physics_qa_node가 만들어둔 상태 —
        # 제안 기능 하나 때문에 턴 전체를 실패시키지 않는다.
        print(f"관심사 제안 판정 실패(턴은 정상 진행): {type(e).__name__}: {e}")
        return {}

    update = {"tokens_used": _add_tokens(state.tokens_used, tokens_used)}
    if not result.should_suggest:
        return update

    thread_id = config["configurable"].get("thread_id", "")
    note = f"이 대화 내용을 관심사로 등록해볼까요? (thread_id: {thread_id})"
    update["comment"] = f"{state.comment}\n\n{note}" if state.comment else note

    # comment에도 남기지만(체크포인트·비-스트리밍 호출용), 실시간 스트림에는 physics_qa_node의
    # "final" 답변 청크가 이미 지나간 뒤라 별도 청크로 흘려보내야 프론트에 실제로 도착한다
    # (위 모듈 주석 "SSE로는 별도 청크로" 참고). get_stream_writer()는 stream_mode="custom"이
    # 아닌 일반 호출(테스트 등)에서는 no-op이라 안전.
    writer = get_stream_writer()
    writer({"suggestion": note})

    return update


graph = StateGraph(ParentState)
graph.add_node("physics_qa", physics_qa_node)
graph.add_node("suggest_interest", suggest_interest_node)
graph.add_edge(START, "physics_qa")
graph.add_edge("physics_qa", "suggest_interest")
graph.add_edge("suggest_interest", END)

# 단기기억(멀티턴)의 저장소 경로 — 이 파일이 소유(위 모듈 docstring 참고). data/ 디렉터리는
# chroma_db/와 같은 성격(바인드 마운트로 컨테이너 재시작에도 살아남아야 하는 영속 데이터)이고,
# 나중에 관심사·실험도구 RDB(앱 데이터, RoadMap "VDB vs RDB" 참고)가 같은 디렉터리에 추가될
# 예정이라 파일은 분리하되(체크포인트는 LangGraph가 스키마를 관리, 앱 데이터는 우리 것)
# 디렉터리는 공유한다 — docker-compose.yml/.gitignore/.dockerignore를 디렉터리 단위로
# 한 번만 설정해두면 나중에 앱 DB 파일이 추가돼도 그 설정들을 다시 안 고쳐도 된다.
CHECKPOINT_DB_PATH = "data/checkpoints.sqlite"

if __name__ == "__main__":
    # 터미널 스모크 테스트 — main.py의 FastAPI lifespan과 정확히 같은 방식(AsyncSqliteSaver)으로
    # 컴파일해서, 이 파일만 실행해도 실제 영속화 경로를 검증할 수 있게 한다. 같은 thread_id로
    # 두 번 실행해보면 재시작 후에도 대화가 이어지는지(디스크 파일에 남아있는지) 확인 가능.
    import asyncio
    import os

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async def _smoke_test():
        os.makedirs(os.path.dirname(CHECKPOINT_DB_PATH), exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as checkpointer:
            app = graph.compile(checkpointer=checkpointer)
            result = await app.ainvoke(
                {"question": "파인만이 설명한 강력이 뭐야?"},
                config={"configurable": {"thread_id": "test"}},
            )
            print(result["answer"])

    asyncio.run(_smoke_test())
