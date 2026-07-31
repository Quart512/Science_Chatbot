import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Literal
from pydantic import Field
from uuid import uuid4

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

import interests
import orchestrator

# SqliteSaver 영속화(6-4, 07-31) — MemorySaver는 프로세스 메모리라 재시작 시 대화가 통째로
# 사라졌는데, 이제 디스크 파일(orchestrator.CHECKPOINT_DB_PATH)에 저장해 재시작에도 살아남는다.
# AsyncSqliteSaver를 쓰는 이유: 동기 SqliteSaver는 astream() 아래서 호출되면 "does not support
# async methods"로 바로 예외가 난다(langgraph_checkpoint_sqlite 실제 소스로 확인) — 이 API가
# astream(stream_mode="custom")을 쓰므로 비동기 버전이 필수.
#
# AsyncSqliteSaver.from_conn_string()은 비동기 컨텍스트 매니저라 요청마다 여닫으면 안 되고
# (연결 비용 + 매번 스키마 setup 반복), 서버가 켜져 있는 동안 한 번만 열어야 한다 — 그래서
# FastAPI의 lifespan에서 열고 app.state에 컴파일된 그래프를 올려둔다. orchestrator.py는 이제
# 컴파일 전 graph 빌더만 export하고(그 파일 모듈 docstring 참고), 실제 컴파일(체크포인터
# 연결)은 여기서 한다 — "무엇을 컴파일할지"(그래프 구조)와 "무엇으로 컴파일할지"(체크포인터,
# 서버 생명주기에 묶임)의 책임을 분리.
@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.path.dirname(orchestrator.CHECKPOINT_DB_PATH), exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(orchestrator.CHECKPOINT_DB_PATH) as checkpointer:
        app.state.graph = orchestrator.graph.compile(checkpointer=checkpointer)
        yield
    # async with 블록을 빠져나가면(서버 종료) 커넥션이 자동으로 닫힘

# fastapi
app = FastAPI(lifespan=lifespan)

# top_k/limit 원값은 물리 QA 능력 내부 다이얼이라 API에 그대로는 안 뺌 — 대신 Claude의 reasoning
# effort와 같은 패턴으로 low/medium/high 프로필만 노출. 실제 숫자 매핑은 graph.py(EFFORT_PROFILES)
# 안에 있고, 여긴 그 이름만 그대로 통과시킨다.
class Query(BaseModel):
    prompt: str
    model: Literal["gemini", "claude", "Qwen-tuned"] = "gemini"
    effort: Literal["low", "medium", "high"] = "medium"
    thread_id: str = Field(default_factory=lambda: str(uuid4()))

# 동기 invoke() -> astream(stream_mode="custom") + SSE로 전환. "custom"은 orchestrator.py의
# physics_qa_node 안에서 get_stream_writer()로 명시적으로 흘려보낸 값만 그대로 받는 채널이라,
# 능력 내부 State가 부모/API로 새어나가지 않으면서도 진행 상황(comment)만 골라 전달할 수 있다.
# 프론트는 각 이벤트에서 final=False인 동안은 진행 로그로, final=True가 뜨면 그게 최종 answer.
#
# request: Request가 필요한 이유(07-31) — lifespan이 app.state에 올려둔 컴파일된 그래프를
# 여기서 꺼내 써야 한다. body(Query)와 이름이 겹치지 않도록 body로 받는다.
@app.post("/query")
async def query(request: Request, body: Query):
    config = {"configurable": {"thread_id": body.thread_id}}
    inputs = {"question": body.prompt, "model": body.model, "effort": body.effort}

    async def event_stream():
        async for chunk in request.app.state.graph.astream(inputs, config=config, stream_mode="custom"):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# 관심사 등록(08-07 호출 경로, 07-31) — "관심사 등록" 버튼이 부르는 평범한 엔드포인트.
# orchestrator.suggest_interest_node가 채팅 답변에 실어 보낸 초안(draft) 필드를 프론트가
# 그대로(또는 사용자가 고친 값으로) 돌려보내면 저장한다. 중복 검사는 이미 제안 시점에
# 끝났으므로 여기서 다시 LLM을 부르지 않는다 — update_existing_id는 그때 알려준
# duplicate.id를 프론트가 그대로 전달하면 됨(설계 논의 참고: 등록은 "그 순간 화면 값을
# 저장하는 평범한 단발 요청"이라 interrupt/재개가 필요 없다는 결론).
#
# interests.py는 표준 라이브러리 sqlite3(동기)로 만들어져 있다 — 그래서 이 핸들러는
# async def가 아니라 평범한 def다. FastAPI는 동기 경로 함수를 스레드풀에서 돌려주므로
# (공식 권장 패턴) 짧은 sqlite3 호출이라도 메인 이벤트 루프(/query의 astream 등)를
# 막지 않는다 — AsyncSqliteSaver를 쓴 이유(체크포인터가 이벤트 루프를 막으면 안 됨)와
# 같은 고려사항을 여기선 "sync 함수를 async def로 감싸지 않는다"로 만족시킨다.
class InterestRegistration(BaseModel):
    title: str
    looking_for: str = ""
    already_known: str = ""
    excluded_topics: str = ""
    # None이면 새로 생성, 값이 있으면 그 id의 기존 관심사를 수정(제안 시 duplicate.id로 받은 값)
    update_existing_id: int | None = None


@app.post("/interests")
def register_interest(body: InterestRegistration):
    if body.update_existing_id is not None:
        updated = interests.update_interest(
            body.update_existing_id,
            title=body.title,
            looking_for=body.looking_for,
            already_known=body.already_known,
            excluded_topics=body.excluded_topics,
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"관심사 id={body.update_existing_id}를 찾을 수 없습니다")
        return {"interest_id": body.update_existing_id, "action": "updated"}

    new_id = interests.create_interest(body.title, body.looking_for, body.already_known, body.excluded_topics)
    return {"interest_id": new_id, "action": "created"}
