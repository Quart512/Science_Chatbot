from typing import Annotated, Literal

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer

import interests
from graph import app as physics_qa_app, _add_tokens
from models import invoke_with_fallback

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


def physics_qa_node(state: ParentState) -> dict:
    # get_stream_writer()는 stream_mode="custom" 스트리밍 중에만 효과 있는 채널 — 일반
    # invoke()에서는 no-op이라 기존 동기 호출(테스트 등)을 깨지 않는다.
    writer = get_stream_writer()

    # fresh invoke() 대신 stream(stream_mode="values")로 돌려서 마지막 스냅샷(=invoke()
    # 반환값과 동일)은 유지하되, 중간 스냅샷의 trace를 진행 상황으로 흘려보낸다.
    result = None
    for snapshot in physics_qa_app.stream({
        "question": state.question,
        "messages": state.messages,
        "model": state.model,
        "effort": state.effort,
        "disabled_models": state.disabled_models,
        "turn_start_len": len(state.messages),
    }, stream_mode="values"):
        result = snapshot
        writer({"trace": result.get("trace", ""), "final": False})

    # 스트림 종료 = final_answer 완료 — answer+comment까지 실어 final=True로 신호.
    writer({"trace": result.get("trace", ""), "answer": result["answer"], "comment": result["comment"], "final": True})

    # 능력이 돌려준 messages는 [기존 이력]+[이번 턴 신규]이므로 뒷부분만 잘라 부모의
    # add_messages reducer에 넘긴다(안 바뀐 옛 메시지까지 매번 교체 시도하는 낭비 방지).
    new_msgs = result["messages"][len(state.messages):]

    return {
        "answer": result["answer"],
        "comment": result["comment"],
        "tokens_used": _add_tokens(state.tokens_used, result["tokens_used"]),
        "disabled_models": result["disabled_models"],
        "messages": new_msgs,
    }


# 관심사 등록 제안 훅 — 물리 QA 답변 뒤에 초안(템플릿)을 만들어 보여준다. 사용자는
# 다음 채팅에서 "이렇게 고쳐줘"라고 하면 이 노드가 다시 돌아 새 초안을 보여주거나,
# 프론트의 "관심사 등록" 버튼으로 저장한다 — interrupt() 기반 독립 그래프로 갔다가
# 폐기한 이력이 있다(RoadMap 참고: "이렇게 고쳐줘"는 이미 정상적인 멀티턴 대화라
# interrupt가 막아주는 문제 자체가 없었음).
#
# physics_qa_node 안이 아니라 별도 노드인 이유: 물리 QA 능력이 관심사 서비스의 존재를
# 몰라야 한다(캡슐화) — 능력 간 제안·연결은 부모(오케스트레이터)의 책임.
#
# SSE는 physics_qa_node의 final=True 청크 "뒤"에 별도 {"suggestion": {...}} 청크로
# 흘려보낸다 — "final"을 "스트림 종료"가 아니라 "답변 도착"으로만 쓰면 그 뒤에 더 보낼 수 있다.
INTEREST_SUGGESTION_MODEL = "gemini"

INTEREST_SUGGESTION_PROMPT = """대화 이력을 보고 사용자가 관심사로 등록할 만한 주제를 반복해서
다루고 있는지 판정해라. 한 번의 가벼운 질문에는 제안하지 마라 — 여러 번 같은 주제를 묻거나
사용자가 스스로 "관심 있다"·"더 알아보고 싶다"는 뜻을 밝혔을 때만 제안해라. 제안할 때는
title/looking_for/already_known/excluded_topics도 대화에 실제로 언급된 내용만으로 채워라 —
대화에 없는 내용을 추론해서 채우지 마라. excluded_topics는 언급이 없으면 빈 문자열로."""

DUP_CHECK_SYSTEM_PROMPT = """기존 관심사 목록과 새 초안을 비교해서 실질적으로 같은 주제를
다루는 기존 항목이 있는지 판정해라. 표현이 달라도 의미가 같으면 중복으로 봐라. 애매하면
중복 아님으로 판정해라 — 잘못 합치는 것보다 따로 두는 게 안전하다."""


class InterestSuggestion(BaseModel):
    should_suggest: bool = Field(
        description="최근 대화를 보고 사용자가 반복적으로 관심 두는 주제가 있어 "
        "관심사로 등록해볼 만하면 True, 아니면 False"
    )
    title: str = Field(default="", description="should_suggest가 True일 때만 채워라 — 관심사 제목")
    looking_for: str = Field(default="", description="should_suggest가 True일 때만 채워라 — 무엇을 찾고 있는지")
    already_known: str = Field(default="", description="should_suggest가 True일 때만 채워라 — 이미 아는 것")
    excluded_topics: str = Field(default="", description="should_suggest가 True일 때만 채워라 — 제외할 주제")


class DuplicateCheck(BaseModel):
    is_duplicate: bool = Field(description="기존 관심사 중 이 초안과 실질적으로 같은 주제가 있으면 True")
    duplicate_id: int | None = Field(default=None, description="겹치는 기존 관심사의 id, 없으면 None")


def _find_duplicate(draft: dict) -> tuple[dict | None, dict]:
    """draft가 기존 관심사와 겹치면 {"id", "title"}을 반환한다(겹치는 게 없거나 관심사
    자체가 없으면 None). title은 LLM이 지어내지 않고 DB 값을 그대로 붙인다 — LLM은
    "겹치나 아니나"와 "어느 id인가"만 판단(id가 실재하는지는 아래서 다시 확인).

    중복 검사 실패(모델 소진 등)는 제안 자체를 막지 않는다 — None 반환, 토큰은 그대로 반영.
    반환: (중복 정보 또는 None, 이번 호출에서 쓴 토큰 — 호출 안 했으면 0)
    """
    zero_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    existing = interests.list_interests()
    if not existing:
        return None, zero_tokens

    existing_text = "\n".join(f"- id={r['id']}: {r['title']}" for r in existing)
    draft_text = f"제목: {draft['title']}\n찾는 것: {draft['looking_for']}"
    messages = [
        SystemMessage(content=DUP_CHECK_SYSTEM_PROMPT),
        HumanMessage(content=f"기존 관심사 목록:\n{existing_text}\n\n새 초안:\n{draft_text}"),
    ]
    try:
        result, _, _, tokens_used = invoke_with_fallback(
            INTEREST_SUGGESTION_MODEL, messages, structured=DuplicateCheck
        )
    except RuntimeError as e:
        print(f"관심사 중복 검사 실패(제안은 계속 진행): {type(e).__name__}: {e}")
        return None, zero_tokens

    if not result.is_duplicate or result.duplicate_id is None:
        return None, tokens_used
    match = next((r for r in existing if r["id"] == result.duplicate_id), None)
    if match is None:  # LLM이 실재하지 않는 id를 댄 경우 — 중복 아님으로 취급(안전한 쪽)
        return None, tokens_used
    return {"id": match["id"], "title": match["title"]}, tokens_used


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

    tokens_used = dict(tokens_used)
    if not result.should_suggest:
        return {"tokens_used": _add_tokens(state.tokens_used, tokens_used)}

    draft = {
        "title": result.title,
        "looking_for": result.looking_for,
        "already_known": result.already_known,
        "excluded_topics": result.excluded_topics,
    }
    duplicate, dup_tokens = _find_duplicate(draft)
    tokens_used = _add_tokens(tokens_used, dup_tokens)

    note = "이 대화 내용을 관심사로 등록해볼까요? 이대로 괜찮으면 아래에서 등록해주세요."
    if duplicate:
        # comment(비-스트리밍 채널)도 문맥을 알 수 있게 — draft/duplicate 구조화 정보는
        # SSE suggestion 청크에만 실린다.
        note += f" (비슷한 관심사 '{duplicate['title']}'가 이미 있어요 — 등록하면 그걸 대신 수정할 수도 있어요)"
    update = {
        "tokens_used": _add_tokens(state.tokens_used, tokens_used),
        "comment": f"{state.comment}\n\n{note}" if state.comment else note,
    }

    # get_stream_writer()는 그래프 실행 컨텍스트 안에서만 안전 — 이 노드를 테스트에서
    # 맨 함수로 직접 부르면(이 저장소 관례) RuntimeError가 나서 방어적으로 감싼다.
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda _: None
    writer({"suggestion": {"note": note, "draft": draft, "duplicate": duplicate}})

    return update


# 라이브러리의 "관심사로 등록" 버튼(명시적 요청)이 부르는 초안 생성 — 그래프 노드가
# 아니라 main.py의 GET /interests/draft가 직접 호출하는 평범한 함수다. suggest_interest_node와
# 로직을 공유하지 않는 이유(RoadMap 08-02 결정): 그쪽의 should_suggest는 "대화에서 이 주제가
# 반복됐는가"를 판정하는 필드인데, 버튼 클릭 자체가 이미 명시적 의도 신호라 그 판정이 무의미하고
# 오히려 위험하다 — 한 번만 언급하고 바로 등록해달라고 해도 "반복 안 됨"으로 판정되면
# InterestSuggestion의 필드 설명("should_suggest가 True일 때만 채워라")대로 LLM이 title 등을
# 빈 채로 돌려줄 수 있다. 그래서 아예 그 질문을 안 묻는 별도 프롬프트+스키마를 쓴다.
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


def draft_interest_from_messages(messages: list[BaseMessage]) -> tuple[dict, dict]:
    """저장은 안 하고 초안만 반환한다 — 저장은 기존 POST /interests가 그대로 담당(재사용).
    중복 검사도 여기선 안 한다(수동 생성 폼도 원래 안 하던 것 — 단순 경로부터, 필요해지면 추가).
    반환: (draft dict, 이번 호출에서 쓴 토큰)
    """
    zero_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    empty_draft = {"title": "", "looking_for": "", "already_known": "", "excluded_topics": ""}
    if not messages:
        return empty_draft, zero_tokens

    llm_messages = [SystemMessage(content=EXPLICIT_INTEREST_DRAFT_PROMPT)] + messages
    try:
        result, _, _, tokens_used = invoke_with_fallback(
            INTEREST_SUGGESTION_MODEL, llm_messages, structured=InterestDraft
        )
    except RuntimeError as e:
        print(f"관심사 초안 생성 실패: {type(e).__name__}: {e}")
        return empty_draft, zero_tokens

    draft = {
        "title": result.title,
        "looking_for": result.looking_for,
        "already_known": result.already_known,
        "excluded_topics": result.excluded_topics,
    }
    return draft, tokens_used


graph = StateGraph(ParentState)
graph.add_node("physics_qa", physics_qa_node)
graph.add_node("suggest_interest", suggest_interest_node)
graph.add_edge(START, "physics_qa")
graph.add_edge("physics_qa", "suggest_interest")
graph.add_edge("suggest_interest", END)

# 단기기억(멀티턴) 저장소 경로 — data/ 디렉터리는 chroma_db/와 같은 성격(바인드 마운트로
# 재시작에도 살아남는 영속 데이터). 앱 데이터 DB(관심사 등)와 파일은 분리하되 디렉터리는
# 공유(docker-compose.yml/.gitignore 설정을 한 번만 하면 되게).
CHECKPOINT_DB_PATH = "data/checkpoints.sqlite"

if __name__ == "__main__":
    # 터미널 스모크 테스트 — main.py의 lifespan과 같은 방식(AsyncSqliteSaver)으로 컴파일해
    # 실제 영속화 경로를 검증한다. 같은 thread_id로 두 번 실행하면 재시작 후에도 대화가 이어지는지 확인 가능.
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
