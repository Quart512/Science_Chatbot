import os
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, RemoveMessage, SystemMessage
from langgraph.config import get_stream_writer

from graph import app as physics_qa_app
from models import MESSAGE_HISTORY_BUDGET_CHARS, add_tokens, invoke_with_fallback

# 부모(오케스트레이터) 그래프 — "표면"이 보는 대화 이력·체크포인터를 소유한다. 능력이
# 물리 QA 하나뿐이라 라우팅 없이 곧장 물리 QA로 간다(추후 라우터 추가 예정).
#
# 능력을 부모 노드로 직접 꽂지 않고 래퍼 함수가 invoke()로 입출력을 명시 매핑하는 이유:
# 능력 내부 State(try_count 등)를 부모가 공유할 이유가 없고, messages를 그냥 공유하면
# 능력 내부의 재시도 초안·tool 메시지가 부모 이력에 섞인다 — 래퍼가 새 메시지만 골라 반환.
#
# 컴파일 전 graph 빌더만 export한다(컴파일=체크포인터 연결은 main.py의 lifespan에서) —
# AsyncSqliteSaver가 비동기 컨텍스트 매니저라 서버 생명주기에 묶여야 하기 때문.


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


def _trim_history(messages: list[BaseMessage], model: str) -> tuple[list[BaseMessage], list[BaseMessage]]:
    """오래된 턴([Human, AI] 쌍 — final_answer의 clean_msgs가 항상 이 짝으로 쌓음)부터
    모델별 문자 예산(MESSAGE_HISTORY_BUDGET_CHARS)을 넘는 만큼 잘라낸다. 결정론적 문자
    수 컷을 쓰는 이유(08-13, LLM 요약 대신): 지금 문제 자체가 "비용 관리"인데 요약은
    LLM 호출을 하나 더 늘려 모순이고, 이 프로젝트가 계속 "판정 대신 계산"을 선호해온
    결과 예측 가능성도 있다. 최소 마지막 한 턴은 예산을 넘더라도 항상 남긴다 — 직전
    질문 맥락 없이 답할 수는 없으므로.
    반환: (남길 메시지, 잘라낼 메시지 — 호출자가 RemoveMessage로 지울 대상)
    """
    budget = MESSAGE_HISTORY_BUDGET_CHARS.get(model)
    if budget is None or len(messages) <= 2:
        return messages, []

    kept_chars = sum(len(m.content) for m in messages[-2:])
    keep_from = len(messages) - 2
    for i in range(len(messages) - 2, 0, -2):
        pair_chars = sum(len(m.content) for m in messages[i - 2:i])
        if kept_chars + pair_chars > budget:
            break
        kept_chars += pair_chars
        keep_from = i - 2

    return messages[keep_from:], messages[:keep_from]


def physics_qa_node(state: ParentState) -> dict:
    # get_stream_writer()는 stream_mode="custom" 스트리밍 중에만 효과 있는 채널 — 일반
    # invoke()에서는 no-op이라 기존 동기 호출(테스트 등)을 깨지 않는다.
    writer = get_stream_writer()

    kept_messages, removed_messages = _trim_history(state.messages, state.model)

    # fresh invoke() 대신 stream(stream_mode="values")로 돌려서 마지막 스냅샷(=invoke()
    # 반환값과 동일)은 유지하되, 중간 스냅샷의 trace를 진행 상황으로 흘려보낸다.
    result = None
    for snapshot in physics_qa_app.stream({
        "question": state.question,
        "messages": kept_messages,
        "model": state.model,
        "effort": state.effort,
        "disabled_models": state.disabled_models,
        "turn_start_len": len(kept_messages),
    }, stream_mode="values"):
        result = snapshot
        writer({"trace": result.get("trace", ""), "final": False})

    # 스트림 종료 = final_answer 완료 — answer+comment까지 실어 final=True로 신호.
    writer({"trace": result.get("trace", ""), "answer": result["answer"], "comment": result["comment"], "final": True})

    # 능력이 돌려준 messages는 [넘긴 이력]+[이번 턴 신규]이므로 뒷부분만 잘라 부모의
    # add_messages reducer에 넘긴다(안 바뀐 옛 메시지까지 매번 교체 시도하는 낭비 방지).
    # 트리밍으로 잘라낸 옛 메시지는 RemoveMessage로 부모 체크포인트에서도 실제로 지운다 —
    # 안 그러면 이번 호출엔 안 보냈어도 SQLite 파일 자체는 계속 커진다.
    new_msgs = result["messages"][len(kept_messages):]
    prune = [RemoveMessage(id=m.id) for m in removed_messages]

    return {
        "answer": result["answer"],
        "comment": result["comment"],
        "tokens_used": add_tokens(state.tokens_used, result["tokens_used"]),
        "disabled_models": result["disabled_models"],
        "messages": prune + new_msgs,
    }


# 관심사 등록 — 라이브러리의 "관심사로 등록" 버튼(명시적 요청)이 부르는 초안 생성.
# 그래프 노드가 아니라 main.py의 GET /interests/draft가 직접 호출하는 평범한 함수다.
#
# 당초(08-07) 이 자리엔 물리 QA 답변 뒤에 매 턴 자동으로 도는 "제안 훅" 노드
# (should_suggest로 "반복해서 관심을 보였는가"를 판정해 제안 여부를 정함 + 유사도
# 기반 중복 검사)가 있었다. 08-02에 버튼 방식으로 통째로 교체하며 삭제했다 —
# 버튼 클릭 자체가 이미 명시적 의도 신호라 "반복됐는가" 판정이 무의미했고(한 번만
# 언급하고 바로 등록해달라고 해도 "반복 안 됨"으로 판정되면 초안 필드가 빈 채로
# 돌아올 위험이 있었다), 매 턴 LLM 호출이 하나 더 느는 비용 대비 얻는 게 적었다
# (RoadMap "메인 챗 라우터 착수 보류" 08-02 후속 참고). 중복 검사 기능도 이때 같이
# 없앴다 — 재활용할 곳이 없어(단순 경로부터, 필요해지면 다시 추가).
INTEREST_DRAFT_MODEL = "gemini"

EXPLICIT_INTEREST_DRAFT_PROMPT = """사용자가 방금 이 대화를 관심사로 등록해달라고 명시적으로
요청했다. 대화 이력을 보고 title/looking_for/already_known/excluded_topics를 채워라 — 대화에
실제로 언급된 내용만 쓰고 없는 내용을 추론해서 채우지 마라. 대화가 너무 짧거나 주제가
불분명하면 title만 대화 맥락에서 최대한 뽑고 나머지는 빈 문자열로 둬라(사용자가 이후 폼에서
직접 채울 수 있다)."""


class InterestDraft(BaseModel):
    title: str = Field(default="", description="관심사 제목")
    looking_for: str = Field(default="", description="무엇을 찾고 있는지")
    already_known: str = Field(default="", description="이미 아는 것")
    excluded_topics: str = Field(default="", description="제외할 주제")


def draft_interest_from_messages(
    messages: list[BaseMessage], disabled_models: list[str] | None = None
) -> tuple[dict, dict, list[str]]:
    """저장은 안 하고 초안만 반환한다 — 저장은 기존 POST /interests가 그대로 담당(재사용).
    중복 검사도 여기선 안 한다(수동 생성 폼도 원래 안 하던 것 — 단순 경로부터, 필요해지면 추가).

    disabled_models: physics_qa_node와 같은 서킷 브레이커(ParentState.disabled_models)를
    호출자(main.py)가 체크포인트에서 읽어 넘겨준다 — 이 함수 자체는 그래프 노드가 아니라
    State에 접근할 수 없으므로 값을 인자로 받고 갱신된 값을 반환해 호출자가 다시 체크포인트에
    쓰게 한다.
    반환: (draft dict, 이번 호출에서 쓴 토큰, 갱신된 disabled_models)
    """
    zero_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    empty_draft = {"title": "", "looking_for": "", "already_known": "", "excluded_topics": ""}
    disabled_models = list(disabled_models) if disabled_models else []
    if not messages:
        return empty_draft, zero_tokens, disabled_models

    # messages는 체크포인트의 실제 대화 이력이라 마지막 턴이 거의 항상 AI 답변이다 —
    # 그 뒤에 아무것도 안 붙이면 메시지 목록이 model(AI) 턴으로 끝나는데, gemini API가
    # 이걸 거부한다("Requests ending with a model turn are not supported", 400
    # INVALID_ARGUMENT — 08-05 라이브 검증 중 실제로 재현). Claude는 받아주지만 gemini가
    # 매번 이 이유로 죽어 fallback으로 새는 데다, invoke_with_fallback이 예외 종류를
    # 구분 안 하고 disabled_models에 추가해버려 이 호출 한 번으로 gemini가 그 스레드의
    # 이후 물리 QA 턴까지 전부 disabled 처리되는 부작용이 있었다(disabled_models가
    # physics_qa_node와 공유되므로). 대화 끝에 사용자 턴을 하나 더 붙여 항상 사용자
    # 턴으로 끝나게 한다 — 새 정보를 추가하는 게 아니라 시스템 프롬프트의 지시를
    # 반복하는 것뿐이라 추출 결과에는 영향이 없다.
    llm_messages = (
        [SystemMessage(content=EXPLICIT_INTEREST_DRAFT_PROMPT)]
        + messages
        + [HumanMessage(content="위 대화를 보고 관심사 초안을 만들어줘.")]
    )
    try:
        result, _, disabled_models, tokens_used = invoke_with_fallback(
            INTEREST_DRAFT_MODEL, llm_messages, structured=InterestDraft, disabled_models=disabled_models
        )
    except RuntimeError as e:
        print(f"관심사 초안 생성 실패: {type(e).__name__}: {e}")
        return empty_draft, zero_tokens, disabled_models

    draft = {
        "title": result.title,
        "looking_for": result.looking_for,
        "already_known": result.already_known,
        "excluded_topics": result.excluded_topics,
    }
    return draft, tokens_used, disabled_models


graph = StateGraph(ParentState)
graph.add_node("physics_qa", physics_qa_node)
graph.add_edge(START, "physics_qa")
graph.add_edge("physics_qa", END)

# 단기기억(멀티턴) 저장소 경로 — data/ 디렉터리는 chroma_db/와 같은 성격(바인드 마운트로
# 재시작에도 살아남는 영속 데이터). 앱 데이터 DB(관심사 등)와 파일은 분리하되 디렉터리는
# 공유(docker-compose.yml/.gitignore 설정을 한 번만 하면 되게).
CHECKPOINT_DB_PATH = "data/checkpoints.sqlite"


def ensure_checkpoint_dir() -> None:
    """CHECKPOINT_DB_PATH의 디렉터리를 만든다 — main.py의 lifespan과 아래 스모크 테스트가
    공유(예전엔 두 곳에 각각 복제돼 있었음). 경로를 디렉터리 없는 파일명만으로 바꾸면
    os.path.dirname()이 ""을 돌려주는데, os.makedirs("")는 FileNotFoundError를 던지므로
    그 경우는 건너뛴다(실제로 겪은 적은 없지만 재현 가능한 버그였음)."""
    dirname = os.path.dirname(CHECKPOINT_DB_PATH)
    if dirname:
        os.makedirs(dirname, exist_ok=True)


if __name__ == "__main__":
    # 터미널 스모크 테스트 — main.py의 lifespan과 같은 방식(AsyncSqliteSaver)으로 컴파일해
    # 실제 영속화 경로를 검증한다. 같은 thread_id로 두 번 실행하면 재시작 후에도 대화가 이어지는지 확인 가능.
    import asyncio

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async def _smoke_test():
        ensure_checkpoint_dir()
        async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as checkpointer:
            app = graph.compile(checkpointer=checkpointer)
            result = await app.ainvoke(
                {"question": "파인만이 설명한 강력이 뭐야?"},
                config={"configurable": {"thread_id": "test"}},
            )
            print(result["answer"])

    asyncio.run(_smoke_test())
