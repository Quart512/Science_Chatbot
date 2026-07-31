from typing import Literal

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

import interests
import orchestrator
from models import invoke_with_fallback

# =========================================================
# 문서 작성기(①⑤ 공용의 관심사 버전) — 독립 그래프. 물리 QA(graph.py)와 달리 orchestrator에
# 얹힌 노드가 아니라 완전히 별개의 그래프다. 이유(설계 논의 참고): interrupt()는 자신이
# 속한 그래프에 체크포인터가 있어야 하는데, 물리 QA는 의도적으로 체크포인터가 없는(매 턴
# fresh invoke) 자식 그래프라 그 패턴을 그대로 못 쓴다. 대신 이 그래프는 orchestrator와
# 같은 체크포인터 파일(orchestrator.CHECKPOINT_DB_PATH)을 재사용하되 thread_id만 다르게
# 쓴다(예: 채팅은 "user-123", 관심사 등록 세션은 "interest-draft-{uuid}") — 파일을 새로
# 만들 필요가 없고, 저장소는 이미 "체크포인트 DB는 대화든 등록 세션이든 다 담는다"는
# 성격이라 자연스럽다.
#
# 두 진입 경로가 여기서 합류한다(설계 논의 참고):
#   - 물리 QA 핸드오프: 사용자가 여러 턴에 걸쳐 관심사를 얘기하면 물리 QA가 "등록할까요?"
#     제안 → 수락 시 그 대화의 thread_id 하나만 넘김(대화 내용을 복사하지 않음 — 6-4로
#     이미 checkpoints.sqlite에 영속화돼 있으므로 draft 노드가 그 thread_id로 다시 읽는다).
#   - 수동 입력: 사용자가 관심사 서비스에서 직접 필드를 채움.
#   두 경로 다음(dup_check → confirm → save)은 완전히 같은 흐름 — 시드가 "LLM이 대화에서
#   뽑은 초안"이냐 "사용자가 쓴 값"이냐만 다르다.
# =========================================================


class InterestWriterState(BaseModel):
    seed_thread_id: str | None = None  # 물리 QA 핸드오프 시 채워짐 — 그 thread_id로 대화 이력을 읽어옴
    model: Literal["gemini", "claude", "Qwen-tuned"] = "gemini"
    title: str = ""
    looking_for: str = ""
    already_known: str = ""
    excluded_topics: str = ""
    duplicate_id: int | None = None  # dup_check가 겹치는 기존 관심사를 찾으면 채움
    duplicate_reasoning: str = ""
    decision: Literal["", "create", "update_existing", "cancel"] = ""  # confirm이 채움
    saved_interest_id: int | None = None  # save가 채움


class InterestDraft(BaseModel):
    title: str = Field(description="관심사 제목 — 짧고 구체적으로 (예: '양자 오류 정정')")
    looking_for: str = Field(description="사용자가 무엇을 찾고 있는지, 대화에 언급된 것만")
    already_known: str = Field(description="사용자가 이미 안다고 말한 것")
    excluded_topics: str = Field(default="", description="제외하고 싶다고 언급한 주제 — 없으면 빈 문자열")


class DuplicateCheck(BaseModel):
    is_duplicate: bool = Field(description="기존 관심사 중 이 초안과 실질적으로 같은 주제가 있으면 True")
    duplicate_id: int | None = Field(default=None, description="겹치는 기존 관심사의 id, 없으면 None")
    reasoning: str = Field(default="", description="판정 근거 한두 문장")


DRAFT_SYSTEM_PROMPT = """대화 내용을 보고 사용자가 등록하려는 관심사를 관심사 템플릿으로 정리해라.
title은 짧고 구체적으로, looking_for/already_known/excluded_topics는 대화에 실제로 언급된 내용만
반영해라 — 대화에 없는 내용을 추론해서 채우지 마라. excluded_topics는 언급이 없으면 빈 문자열로."""

DUP_CHECK_SYSTEM_PROMPT = """기존 관심사 목록과 새 초안을 비교해서 실질적으로 같은 주제를 다루는
기존 항목이 있는지 판정해라. 표현이 달라도 의미가 같으면 중복으로 봐라. 애매하면 중복 아님으로
판정해라 — 잘못 합치는 것보다 따로 두는 게 안전하다."""


async def draft(state: InterestWriterState, config: RunnableConfig) -> dict:
    """seed_thread_id가 있고 title이 비어있으면(물리 QA 핸드오프) 그 thread의 대화 이력을
    읽어 LLM으로 템플릿을 채운다. 이미 title이 채워져 있으면(수동 입력) 그대로 통과 —
    LLM 호출 0. seed_thread_id가 없는데 title도 비어있으면(잘못된 호출) 빈 채로 둔다 —
    다음 단계(dup_check)가 빈 제목으로 실행돼도 안전하게 동작하지만, 실제 등록은 confirm
    단계에서 사용자가 빈 초안을 보고 취소할 수 있다.

    config["configurable"]["qa_checkpointer"]로 orchestrator의 체크포인터 인스턴스를
    받는다(의존성 주입) — orchestrator.graph를 그 체크포인터로 다시 컴파일해 thread state를
    읽는다. 대화를 복사해서 넘기지 않고 thread_id 하나만 받는 이유는 모듈 docstring 참고.
    """
    if not state.seed_thread_id or state.title:
        return {}

    checkpointer = config["configurable"]["qa_checkpointer"]
    qa_app = orchestrator.graph.compile(checkpointer=checkpointer)
    qa_state = await qa_app.aget_state({"configurable": {"thread_id": state.seed_thread_id}})
    history = qa_state.values.get("messages", []) if qa_state.values else []
    if not history:
        return {}

    history_text = "\n".join(f"{m.type}: {m.content}" for m in history)
    messages = [
        SystemMessage(content=DRAFT_SYSTEM_PROMPT),
        HumanMessage(content=history_text),
    ]
    extraction, _, _, _ = invoke_with_fallback(state.model, messages, structured=InterestDraft)
    return {
        "title": extraction.title,
        "looking_for": extraction.looking_for,
        "already_known": extraction.already_known,
        "excluded_topics": extraction.excluded_topics,
    }


def dup_check(state: InterestWriterState) -> dict:
    """등록된 관심사 전체를 프롬프트에 넣고 LLM에게 중복 여부를 묻는다 — 수십 개 규모라
    임베딩 유사도보다 이 방식이 더 정확하다는 게 이미 내린 결정(RoadMap "VDB vs RDB"
    설계 노트). 관심사가 하나도 없으면 물어볼 대상이 없으므로 LLM 호출 없이 통과."""
    existing = interests.list_interests()
    if not existing:
        return {}

    existing_text = "\n".join(
        f"- id={r['id']}: {r['title']} (찾는 것: {r['looking_for']})" for r in existing
    )
    draft_text = (
        f"제목: {state.title}\n찾는 것: {state.looking_for}\n"
        f"아는 것: {state.already_known}\n제외 주제: {state.excluded_topics}"
    )
    messages = [
        SystemMessage(content=DUP_CHECK_SYSTEM_PROMPT),
        HumanMessage(content=f"기존 관심사 목록:\n{existing_text}\n\n새 초안:\n{draft_text}"),
    ]
    result, _, _, _ = invoke_with_fallback(state.model, messages, structured=DuplicateCheck)
    if result.is_duplicate:
        return {"duplicate_id": result.duplicate_id, "duplicate_reasoning": result.reasoning}
    return {}


def confirm(state: InterestWriterState) -> dict:
    """유일하게 interrupt()를 부르는 노드 — 그리고 재개(Command(resume=...)) 시 이 노드
    "전체"가 처음부터 다시 실행된다(langgraph.types.interrupt 소스 확인, 설계 논의 참고).
    그래서 이 노드 안에서는 LLM·DB 호출을 절대 하지 않는다 — draft/dup_check가 이미
    끝내놓은 state 값을 읽어 보여주기만 하고, interrupt()의 반환값(재개 시 사용자가
    Command(resume=...)로 넘긴 값)을 그대로 분기해서 decision에 채운다.

    resume 값 형태: {"action": "create"|"update_existing"|"cancel", "edits": {선택, 필드
    덮어쓰기}}. dict가 아니거나 action이 없으면 안전하게 "cancel"로 취급 — 잘못 해석해서
    사용자 확인 없이 저장하는 것보다 취소되는 쪽이 안전하다.
    """
    payload = {
        "draft": {
            "title": state.title,
            "looking_for": state.looking_for,
            "already_known": state.already_known,
            "excluded_topics": state.excluded_topics,
        },
        "duplicate_id": state.duplicate_id,
        "duplicate_reasoning": state.duplicate_reasoning,
    }
    resume_value = interrupt(payload)

    if not isinstance(resume_value, dict):
        resume_value = {}
    action = resume_value.get("action", "cancel")
    if action not in ("create", "update_existing", "cancel"):
        action = "cancel"

    result: dict = {"decision": action}
    edits = resume_value.get("edits") or {}
    for field in ("title", "looking_for", "already_known", "excluded_topics"):
        if field in edits:
            result[field] = edits[field]
    return result


def save(state: InterestWriterState) -> dict:
    if state.decision == "create":
        new_id = interests.create_interest(
            state.title, state.looking_for, state.already_known, state.excluded_topics
        )
        return {"saved_interest_id": new_id}
    if state.decision == "update_existing" and state.duplicate_id is not None:
        interests.update_interest(
            state.duplicate_id,
            title=state.title,
            looking_for=state.looking_for,
            already_known=state.already_known,
            excluded_topics=state.excluded_topics,
        )
        return {"saved_interest_id": state.duplicate_id}
    return {}


def route_after_confirm(state: InterestWriterState) -> Literal["save", "cancelled"]:
    return "save" if state.decision in ("create", "update_existing") else "cancelled"


graph = StateGraph(InterestWriterState)
graph.add_node("draft", draft)
graph.add_node("dup_check", dup_check)
graph.add_node("confirm", confirm)
graph.add_node("save", save)

graph.add_edge(START, "draft")
graph.add_edge("draft", "dup_check")
graph.add_edge("dup_check", "confirm")
graph.add_conditional_edges("confirm", route_after_confirm, {"save": "save", "cancelled": END})
graph.add_edge("save", END)

# 체크포인터 파일은 orchestrator와 공유(모듈 docstring 참고) — 새로 만들지 않는다.
CHECKPOINT_DB_PATH = orchestrator.CHECKPOINT_DB_PATH


if __name__ == "__main__":
    # 터미널 스모크 테스트 — 수동 입력 경로로 등록 1건을 실제로 confirm까지 진행.
    # interrupt() 자체를 확인하려면 아래처럼 두 번 실행(1차: 멈추는지, 2차: Command(resume=...)로
    # 재개)해야 한다 — 이 블록은 1차(멈추는지)만 보여준다.
    import asyncio

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async def _smoke_test():
        async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as checkpointer:
            app = graph.compile(checkpointer=checkpointer)
            config = {
                "configurable": {
                    "thread_id": "interest-draft-smoke-test",
                    "qa_checkpointer": checkpointer,
                }
            }
            result = await app.ainvoke(
                {"title": "테스트 관심사", "looking_for": "테스트용 입력"}, config
            )
            print("1차 실행 결과(멈춰야 함):", result)

    asyncio.run(_smoke_test())
