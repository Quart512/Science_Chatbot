import asyncio
import json
import os
import tempfile
from contextlib import asynccontextmanager

import fitz
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Literal
from pydantic import Field
from uuid import uuid4

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

import interests
import orchestrator
import paper.paper_ingest as paper_ingest
import paper_catalog
import paper_recommend

# AsyncSqliteSaver로 대화를 디스크에 영속화(재시작에도 살아남음) — 동기 SqliteSaver는
# astream() 아래서 예외가 나 비동기 버전이 필수. 컨텍스트 매니저를 요청마다 여닫을 수
# 없어 lifespan에서 한 번만 열고 app.state에 컴파일된 그래프를 올려둔다 — orchestrator.py는
# graph 구조만, 체크포인터 연결(컴파일)은 여기서 책임진다.
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

# astream(stream_mode="custom") + SSE — "custom"은 physics_qa_node가 get_stream_writer()로
# 명시적으로 흘려보낸 값만 받는 채널이라 능력 내부 State가 새지 않는다. final=False는
# 진행 로그, final=True가 최종 answer. request는 lifespan이 올려둔 컴파일된 그래프를
# 꺼내 쓰기 위함.
@app.post("/query")
async def query(request: Request, body: Query):
    config = {"configurable": {"thread_id": body.thread_id}}
    inputs = {"question": body.prompt, "model": body.model, "effort": body.effort}

    async def event_stream():
        async for chunk in request.app.state.graph.astream(inputs, config=config, stream_mode="custom"):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# "관심사 등록" 버튼(라이브러리 폼)이 부르는 엔드포인트 — GET /interests/draft가 만든
# 초안을 프론트가 그대로(또는 고쳐서) 돌려보내면 저장. 중복 검사는 없다(08-02에 통째로
# 삭제 — RoadMap "메인 챗 라우터 착수 보류" 참고).
#
# 아래 sqlite3 기반 엔드포인트들은 전부 평범한 def(async 아님) — FastAPI가 스레드풀에서
# 돌려주므로 짧은 동기 DB 호출도 /query의 이벤트 루프를 막지 않는다.
class InterestRegistration(BaseModel):
    title: str
    looking_for: str = ""
    already_known: str = ""
    excluded_topics: str = ""
    # None이면 새로 생성, 값이 있으면 그 id의 기존 관심사를 수정(제안 시 duplicate.id로 받은 값)
    update_existing_id: int | None = None



@app.get("/interests")
def list_interests():
    return {"interests": interests.list_interests()}


# 챗 사이드바 "관심사로 등록" 버튼이 부르는 엔드포인트 — 저장은 안 하고 초안만 반환한다
# (라이브러리 관심사 탭의 "새 관심사 만들기" 폼을 이 값으로 프리필한 뒤, 저장은 그 폼이
# 기존 POST /interests를 그대로 호출). 체크포인트 조회(aget_state)가 AsyncSqliteSaver
# 전용이라 async def가 필수 — 그 안의 LLM 호출(invoke_with_fallback)은 동기 함수라
# asyncio.to_thread로 감싸 이벤트 루프를 막지 않는다(/query와 달리 그래프를 안 타므로
# LangGraph가 알아서 스레드로 돌려주는 처리가 없다).
#
# disabled_models(모델 서킷 브레이커)도 physics_qa_node와 같은 체크포인트에서 읽고 쓴다 —
# 그래프를 안 타는 1회성 호출이지만 결국 같은 ParentState를 보는 orchestrator 안의
# 함수이므로, 이미 읽어온 스냅샷에서 같이 꺼내 쓰고(공짜) 갱신됐으면 aupdate_state로
# 다시 써준다. 그래야 여기서 gemini가 소진됐다는 걸 알아내면 다음 /query 턴이나 다음
# 클릭이 그 사실을 재발견하지 않고 곧장 claude로 간다.
@app.get("/interests/draft")
async def draft_interest(request: Request, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await request.app.state.graph.aget_state(config)
    messages = snapshot.values.get("messages", [])
    disabled_models = snapshot.values.get("disabled_models", [])
    draft, _, updated_disabled_models = await asyncio.to_thread(
        orchestrator.draft_interest_from_messages, messages, disabled_models
    )
    # snapshot.values가 비어있으면(한 번도 /query가 안 돈 thread) ParentState.question이
    # 없는 상태라 aupdate_state가 다음 태스크를 계산하려다 Pydantic 검증에서 터진다(실제로
    # 재현·확인함) — 이 경우는 애초에 messages도 비어있어 draft_interest_from_messages가
    # disabled_models를 안 바꾸므로(빈 메시지면 곧장 반환) 아래 조건에서 자연히 걸러진다.
    # as_node="__start__"가 필요한 이유도 실제로 재현해서 확인함 — 그래프 노드가 실행한
    # 게 아니라 값을 직접 주입하는 것이므로 LangGraph가 "어느 노드의 쓰기로 취급할지"를
    # 스스로 못 정해 as_node 없인 InvalidUpdateError("Ambiguous update")를 던진다.
    if snapshot.values and updated_disabled_models != disabled_models:
        await request.app.state.graph.aupdate_state(
            config, {"disabled_models": updated_disabled_models}, as_node="__start__"
        )
    return draft


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


# interest_paper 조인 테이블이 없어 관심사 삭제는 interests 행 하나만 지운다 —
# 그 관심사가 추천한 카탈로그 행을 같이 지울지는 조인 테이블이 생길 때 정한다.
@app.delete("/interests/{interest_id}")
def delete_interest(interest_id: int):
    deleted = interests.delete_interest(interest_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"관심사 id={interest_id}를 찾을 수 없습니다")
    return {"interest_id": interest_id, "action": "deleted"}


# "관심사에서 트리거할 때만" 실행(cron 아님) — 라이브러리 관심사 카드의 검색 버튼만
# 호출한다. 결과를 한 번에 돌려주는 단순한 형태(스트리밍은 필요해지면 SSE로 전환).
# start는 페이지네이션 오프셋 — "추가 검색"이 다음 순위부터 이어받는다.
@app.post("/interests/{interest_id}/search")
def trigger_recommend_search(interest_id: int, start: int = 0):
    try:
        results = paper_recommend.recommend_for_interest(interest_id, start=start)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"recommended": results}


class RefreshRequest(BaseModel):
    # /search가 돌려준 값을 프론트가 그대로 되돌려보내는 echo라 항목마다 엄격한
    # 스키마를 둘 이득이 적다(사용자가 직접 입력하는 폼이 아님) — 느슨한 dict로 받는다.
    existing_candidates: list[dict] = []


# 관심사 수정 직후 프론트가 호출 — /search와 달리 세션에 쌓인 기존 후보 목록을 같이
# 받아 refresh_for_interest()가 재스크리닝+병합까지 한다(그 함수 docstring 참고).
@app.post("/interests/{interest_id}/refresh")
def refresh_recommend_search(interest_id: int, body: RefreshRequest):
    try:
        results = paper_recommend.refresh_for_interest(interest_id, body.existing_candidates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"recommended": results}


# register_paper()가 pdf_path(디스크 경로)를 받으므로 업로드 바이트를 임시 파일에
# 써서 넘긴다. fitz.FileDataError(유효하지 않은 PDF)는 사용자 입력 검증 경계라 400으로.
@app.post("/papers")
def register_paper_endpoint(
    file: UploadFile = File(...),
    doi: str | None = Form(None),
    arxiv_id: str | None = Form(None),
):
    file_bytes = file.file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        try:
            return paper_ingest.register_paper(tmp.name, doi=doi, arxiv_id=arxiv_id)
        except fitz.FileDataError:
            raise HTTPException(status_code=400, detail="PDF로 열 수 없는 파일입니다")


# status로 필터링(recommended/owned/dismissed) — 관심사별 필터는 interest_paper 조인
# 테이블이 없어 아직 불가(RoadMap "관심사↔논문이 다대다다" 참고), 전역 목록만 가능.
@app.get("/papers")
def list_papers(status: Literal["recommended", "owned", "dismissed"] | None = None):
    return {"papers": paper_catalog.list_papers(status=status)}
