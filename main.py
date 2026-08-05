import asyncio
import json
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import os

import fitz
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Literal
from pydantic import Field
from uuid import uuid4

from langchain_core.messages import RemoveMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

import api_keys
import equipment
import interests
import knowledge_notes
import orchestrator
import paper.paper_ingest as paper_ingest
import paper_catalog
import paper_recommend
import research_branches
import research_notes
import research_sessions
import research_workflow
from models import ContextBudgetExceeded

# AsyncSqliteSaver로 대화를 디스크에 영속화(재시작에도 살아남음) — 동기 SqliteSaver는
# astream() 아래서 예외가 나 비동기 버전이 필수. 컨텍스트 매니저를 요청마다 여닫을 수
# 없어 lifespan에서 한 번만 열고 app.state에 컴파일된 그래프를 올려둔다 — orchestrator.py는
# graph 구조만, 체크포인터 연결(컴파일)은 여기서 책임진다. 연구 워크플로우(⑥)도 State
# 스키마가 다른 독립 그래프라 체크포인터·컴파일된 그래프를 따로 둔다(research_workflow.py
# 모듈 docstring 참고 — 두 그래프는 애초에 State를 공유하지 않는다).
@asynccontextmanager
async def lifespan(app: FastAPI):
    orchestrator.ensure_checkpoint_dir()
    research_workflow.ensure_checkpoint_dir()
    async with (
        AsyncSqliteSaver.from_conn_string(orchestrator.CHECKPOINT_DB_PATH) as checkpointer,
        AsyncSqliteSaver.from_conn_string(research_workflow.CHECKPOINT_DB_PATH) as research_checkpointer,
    ):
        app.state.graph = orchestrator.graph.compile(checkpointer=checkpointer)
        app.state.research_graph = research_workflow.graph.compile(checkpointer=research_checkpointer)
        yield
    # async with 블록을 빠져나가면(서버 종료) 커넥션이 자동으로 닫힘

# fastapi
app = FastAPI(lifespan=lifespan)

# 08-04 React 프론트 전환 착수 전까진 필요 없었다 — Streamlit은 서버 쪽(streamlit 프로세스)
# 에서 requests로 이 API를 호출해 브라우저 CORS가 아예 안 걸렸는데, 브라우저가 직접
# fetch하는 새 프론트가 생기면서 처음 필요해짐. 프런트 개발 서버 포트(Vite 기본 5173)를
# 환경변수로 오버라이드 가능하게(frontend/common.py의 BACKEND_URL과 같은 패턴) —
# 배포 시 실제 도메인으로 바뀌어야 하므로 와일드카드 대신 명시적 목록을 유지한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# /api 응답에 브라우저가 캐싱하지 못하게 명시(08-05, 설정 화면 개발 중 실제로 겪은 버그).
# FastAPI는 기본적으로 Cache-Control을 안 붙이는데, 그 상태에서 어떤 이유로든 /api
# 경로가 한 번이라도 캐싱 가능한 응답(예: SPA 폴백의 FileResponse가 ETag/Last-Modified를
# 자동으로 붙인 index.html)을 준 적이 있으면, 브라우저가 그 뒤로도 진짜 API 응답 대신
# 캐싱된 옛 응답을 계속 재사용한다 — 실제로 이 경로 분리(/api) 작업 도중 재현: 서버
# 코드를 고쳐 재시작해도 브라우저가 예전 응답을 계속 돌려줘서 원인 파악에 시간이 걸렸다.
# REST API는 애초에 캐싱 대상이 아니므로(정적 자산 /assets/*는 Vite가 파일명에 해시를
# 붙여 그대로 장기 캐싱돼도 안전 — 여긴 안 건드림) 아예 원천 차단한다.
@app.middleware("http")
async def no_cache_for_api(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

# 설치판 실행 스크립트(.command/.bat, 08-05 Docker 패키징)가 폴링할 가벼운 대상 — DB나
# 임베딩 모델을 안 건드리는 순수 응답. lifespan이 끝나야(bge-m3 로딩 완료 후) 이 라우트
# 자체가 응답 가능해지므로, 200이 오는 순간 곧 "서버가 실제로 요청을 받을 준비가 됐다"는
# 뜻이다 — 실측(08-05): 처음 받는 bge-m3 다운로드 포함 시 최대 2~3분까지 걸릴 수 있었다.
@app.get("/api/health")
def health():
    return {"status": "ok"}

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
@app.post("/api/query")
async def query(request: Request, body: Query):
    config = {"configurable": {"thread_id": body.thread_id}}
    inputs = {"question": body.prompt, "model": body.model, "effort": body.effort}

    async def event_stream():
        async for chunk in request.app.state.graph.astream(inputs, config=config, stream_mode="custom"):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# 메시지 트리밍 2단계 — 수동 삭제(08-13 1단계 자동 트리밍 후속, RoadMap "🔄 진행 중"
# 참고). 화면(ChatPanel)이 그리는 이력은 지금 SSE로 받은 조각을 조립한 세션 로컬
# state라 백엔드 체크포인트의 실제 메시지 id가 없다 — 이 엔드포인트가 체크포인트의
# 진짜 목록(id 포함)을 내려줘야 프론트가 "이 메시지를 지워줘"를 구체적인 id로 요청할
# 수 있다. role은 BaseMessage.type("human"/"ai")을 프론트 계약("user"/"assistant")에
# 맞게 변환 — orchestrator.ParentState.messages는 physics_qa_node가 항상 Human/AI
# 쌍만 쌓으므로(SystemMessage는 능력 내부에서만 쓰고 부모로 안 올라옴) 그 외 타입은
# 원래 값을 그대로 둔다(향후 실제로 나오면 그때 대응).
_MESSAGE_TYPE_TO_ROLE = {"human": "user", "ai": "assistant"}


@app.get("/api/query/{thread_id}/messages")
async def get_query_messages(request: Request, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await request.app.state.graph.aget_state(config)
    messages = snapshot.values.get("messages", [])
    return {
        "messages": [
            {"id": m.id, "role": _MESSAGE_TYPE_TO_ROLE.get(m.type, m.type), "content": m.content}
            for m in messages
        ]
    }


# 특정 메시지 하나만 체크포인트에서 지운다 — RemoveMessage가 add_messages reducer의
# 특수 신호라, 그래프 노드 실행 없이(LLM 호출 없이) aupdate_state로 값만 주입해도
# 정확히 그 id만 지워짐을 직접 재현해 확인함(RoadMap 참고). orchestrator._trim_history가
# 예산 초과분을 자동으로 지울 때 쓰는 것과 같은 메커니즘을, 여기서는 사용자가 특정 id
# 하나를 지목한 경우에 쓴다.
@app.delete("/api/query/{thread_id}/messages/{message_id}")
async def delete_query_message(request: Request, thread_id: str, message_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    await request.app.state.graph.aupdate_state(
        config, {"messages": [RemoveMessage(id=message_id)]}, as_node="__start__"
    )
    return {"deleted_id": message_id}


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



@app.get("/api/interests")
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
@app.get("/api/interests/draft")
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


@app.post("/api/interests")
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


# interest_paper(관심사가 스크리닝한 논문 기록)도 같이 지운다 — 08-04 실사용 중
# 발견한 버그: 이 조인 행을 안 지우면 삭제한 관심사가 남긴 recommended 논문·스크리닝
# 기록이 고아로 남아 "관심사와 무관한데 recommended"로 혼란을 준다. interest_paper는
# paper_catalog.py가 스키마를 소유해서 그쪽 함수를 통해 지운다(순환 import 방지).
@app.delete("/api/interests/{interest_id}")
def delete_interest(interest_id: int):
    paper_catalog.delete_screenings_for_interest(interest_id)
    deleted = interests.delete_interest(interest_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"관심사 id={interest_id}를 찾을 수 없습니다")
    return {"interest_id": interest_id, "action": "deleted"}


# "관심사에서 트리거할 때만" 실행(cron 아님) — 라이브러리 관심사 카드의 검색 버튼만
# 호출한다. 결과를 한 번에 돌려주는 단순한 형태(스트리밍은 필요해지면 SSE로 전환).
# start는 페이지네이션 오프셋 — "추가 검색"이 다음 순위부터 이어받는다.
@app.post("/api/interests/{interest_id}/search")
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
@app.post("/api/interests/{interest_id}/refresh")
def refresh_recommend_search(interest_id: int, body: RefreshRequest):
    try:
        results = paper_recommend.refresh_for_interest(interest_id, body.existing_candidates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"recommended": results}


# interest_paper 조인 조회 — /search·/refresh는 그 순간의 스크리닝 결과만 응답으로
# 돌려주고 저장은 안 했었다(08-03 전까지). 이제 record_screening()이 매 스크리닝을
# 남기므로, 세션이 끊긴 뒤에도 "이 관심사에 무엇이 추천됐는지"를 다시 조회할 수 있다.
@app.get("/api/interests/{interest_id}/papers")
def list_interest_papers(interest_id: int, only_relevant: bool = False):
    if interests.get_interest(interest_id) is None:
        raise HTTPException(status_code=404, detail=f"관심사 id={interest_id}를 찾을 수 없습니다")
    return {"papers": paper_catalog.list_papers_for_interest(interest_id, only_relevant=only_relevant)}


# register_paper()가 pdf_path(디스크 경로)를 받으므로 업로드 바이트를 임시 파일에
# 써서 넘긴다. fitz.FileDataError(유효하지 않은 PDF)는 사용자 입력 검증 경계라 400으로.
@app.post("/api/papers")
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
            return paper_ingest.register_paper(
                tmp.name, doi=doi, arxiv_id=arxiv_id, filename=file.filename or ""
            )
        except fitz.FileDataError:
            raise HTTPException(status_code=400, detail="PDF로 열 수 없는 파일입니다")


# status로 필터링(recommended/owned/dismissed) — 관심사별 필터는 interest_paper 조인
# 테이블이 없어 아직 불가(RoadMap "관심사↔논문이 다대다다" 참고), 전역 목록만 가능.
@app.get("/api/papers")
def list_papers(status: Literal["recommended", "owned", "dismissed"] | None = None):
    return {"papers": paper_catalog.list_papers(status=status)}


# 논문 내용 조회(08-03) — get_paper_summary()는 이미 있었지만 지금까지 어디서도 호출을
# 안 해서 API로 노출된 적이 없었다. 논문은 원본(PDF)이 따로 있는 불변 소스라 수정
# 엔드포인트는 안 둔다(잘못됐으면 재등록하거나 기각 — equipment/notes와 다른 지점).
@app.get("/api/papers/{paper_id}/summary")
def get_paper_summary_endpoint(paper_id: str):
    try:
        result = paper_ingest.get_paper_summary(paper_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"paper_id={paper_id}가 등록돼 있지 않습니다")
    except ContextBudgetExceeded as e:
        raise HTTPException(status_code=422, detail=f"논문이 길어 요약을 생성할 수 없습니다: {e}")
    return {**result, "extraction": result["extraction"].model_dump()}


# 원본 조회 ③(08-05) — 화면에 [CITE:...] 마커·재청킹된 조각 대신 원문 그대로를 보여준다
# (설계 노트 "논문·노트 저장 방식 재설계" 참고). file_path는 ②-B "트래킹에 추가"로
# 등록된 논문에만 있다 — 기존 업로드 다이얼로그 경로(tempfile만 쓰고 버림)로 등록된
# 논문은 원본이 아예 없으므로 404. resolve_library_path()는 file_path가 DB에서 온
# 값이라 신뢰할 수 있는 입력이지만, ②-B가 쓰는 것과 같은 함수를 그대로 재사용해
# 방어를 이중으로 겹치는 값이 크다("경로 검증은 한 곳"이 깨질 위험 없이 공짜로 붙음).
@app.get("/api/papers/{paper_id}/file")
def get_paper_file(paper_id: str):
    paper = paper_catalog.get_paper(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"paper_id={paper_id}가 등록돼 있지 않습니다")
    if not paper["file_path"]:
        raise HTTPException(status_code=404, detail="이 논문은 원본 파일이 추적되어 있지 않습니다")
    try:
        abs_path = paper_catalog.resolve_library_path(paper["file_path"])
    except ValueError:
        raise HTTPException(status_code=400, detail="library/ 루트를 벗어난 경로입니다")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="원본 파일을 찾을 수 없습니다 — 이동되었거나 삭제되었을 수 있습니다")
    return FileResponse(
        abs_path,
        media_type="application/pdf",
        filename=os.path.basename(paper["file_path"]),
        content_disposition_type="inline",
    )


# 서버측 파일 브라우저 ②-A(08-05) — library/를 스캔만 한다. 브라우저가 파일의 전체
# 경로를 안 줘서 업로드 다이얼로그로 library/를 열 방법이 없다는 게 이 방식으로 간
# 이유(RoadMap 설계 노트 항목 A). "트래킹에 추가"(②-B)는 아직 없고 이 엔드포인트는
# 목록만 보여준다.
@app.get("/api/library/files")
def list_library_files():
    return {"files": paper_catalog.scan_library_files()}


# "트래킹에 추가" ②-B(08-05), ④에서 비동기로 전환(08-05) — 여기서는 사용자가 준
# 상대경로를 검증해 절대경로로 바꾸는 것까지만 동기로 하고, 무거운 파싱·청킹·임베딩은
# paper_ingest.track_in_background()가 백그라운드 스레드로 넘긴다(설계 노트 항목 G).
# 그래서 fitz.FileDataError 같은 파싱 실패는 더 이상 여기서 400으로 안 잡힌다 — 그
# 시점엔 이미 응답이 나간 뒤라 analysis_status="failed"로만 반영된다(폴링으로 확인).
class LibraryTrackRequest(BaseModel):
    path: str


@app.post("/api/library/track")
def track_library_file(body: LibraryTrackRequest):
    try:
        abs_path = paper_catalog.resolve_library_path(body.path)
    except ValueError:
        raise HTTPException(status_code=400, detail="library/ 루트를 벗어난 경로입니다")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail=f"library/{body.path} 파일을 찾을 수 없습니다")
    return paper_ingest.track_in_background(
        abs_path, file_path=body.path, filename=os.path.basename(body.path)
    )


# 실험도구 DB(⑤) — /interests와 완전히 같은 패턴(그래프도 LLM 호출도 없는 순수 CRUD).
# update_existing_id도 InterestRegistration과 같은 계약: None이면 새로 생성, 값이 있으면
# 그 id를 수정.
#
# 선택 필드가 `""`가 아니라 `None` 기본값인 이유: 수정 시 "명시 안 함"과 "빈 값으로
# 설정"을 구분해야 한다. `""`가 기본값이면 이름만 고쳐 보낸 요청이 precautions(안전
# 주의사항)까지 조용히 지운다 — register_paper()의 `{"title": None}` 버그와 같은 종류다.
class EquipmentRegistration(BaseModel):
    name: str
    purpose: str | None = None
    detail: str | None = None
    # 연구 워크플로우의 안전 가드레일(check_equipment_precautions)이 읽는다 — 이 장비가
    # 실험 설계에 등장하면 이 문구를 그대로 사용자에게 보여준다.
    precautions: str | None = None
    update_existing_id: int | None = None


@app.get("/api/equipment")
def list_equipment():
    return {"equipment": equipment.list_equipment()}


@app.post("/api/equipment")
def register_equipment(body: EquipmentRegistration):
    # None(= 명시 안 함)인 필드는 아예 빼서 넘긴다 — update_equipment()가 **fields로
    # 받은 것만 SET 하는 부분 갱신이라, 안 넘기면 기존 값이 그대로 유지된다.
    optional = {
        k: v for k, v in
        (("purpose", body.purpose), ("detail", body.detail), ("precautions", body.precautions))
        if v is not None
    }

    if body.update_existing_id is not None:
        updated = equipment.update_equipment(body.update_existing_id, name=body.name, **optional)
        if not updated:
            raise HTTPException(status_code=404, detail=f"실험도구 id={body.update_existing_id}를 찾을 수 없습니다")
        return {"equipment_id": body.update_existing_id, "action": "updated"}

    # 생성 시 빠진 필드는 create_equipment()의 기본값 ""가 채운다(컬럼이 NOT NULL).
    new_id = equipment.create_equipment(body.name, **optional)
    return {"equipment_id": new_id, "action": "created"}


@app.delete("/api/equipment/{equipment_id}")
def delete_equipment(equipment_id: int):
    deleted = equipment.delete_equipment(equipment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"실험도구 id={equipment_id}를 찾을 수 없습니다")
    return {"equipment_id": equipment_id, "action": "deleted"}


# 지식 노트(08-03) — /equipment와 같은 패턴이되, text는 편집이 일급 연산이라(RoadMap
# "편집이 일급 연산이다" 참고) None 기본값으로 "명시 안 함"과 "빈 값" 구분 필요.
class NoteRegistration(BaseModel):
    title: str | None = None
    text: str | None = None
    update_existing_id: int | None = None


@app.get("/api/notes")
def list_notes():
    return {"notes": knowledge_notes.list_notes()}


@app.post("/api/notes")
def register_note(body: NoteRegistration):
    optional = {
        k: v for k, v in (("title", body.title), ("text", body.text))
        if v is not None
    }

    if body.update_existing_id is not None:
        updated = knowledge_notes.update_note(body.update_existing_id, **optional)
        if not updated:
            raise HTTPException(status_code=404, detail=f"노트 id={body.update_existing_id}를 찾을 수 없습니다")
        return {"note_id": body.update_existing_id, "action": "updated"}

    new_id = knowledge_notes.create_note(**optional)
    return {"note_id": new_id, "action": "created"}


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: int):
    deleted = knowledge_notes.delete_note(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"노트 id={note_id}를 찾을 수 없습니다")
    return {"note_id": note_id, "action": "deleted"}


# 설정 화면(08-05) — 사용자 API 키 입력. RoadMap "싱글 유저 로컬 앱 확정" 결정("API 키는
# 사용자 본인 입력") 참고. 조회는 마스킹된 상태만 돌려주고 평문 키를 다시 내려주지 않는다
# — 저장된 키를 화면에 다시 보여줄 일이 없어서(있음/끝자리만 표시) 그럴 이유가 없다.
class ApiKeyRegistration(BaseModel):
    provider: Literal["gemini", "claude"]
    api_key: str


@app.get("/api/settings/keys")
def list_api_key_status():
    return {"keys": api_keys.list_key_status()}


@app.post("/api/settings/keys")
def save_api_key(body: ApiKeyRegistration):
    if not body.api_key.strip():
        raise HTTPException(status_code=400, detail="api_key는 빈 문자열일 수 없습니다")
    api_keys.set_api_key(body.provider, body.api_key.strip())
    return {"provider": body.provider, "action": "saved"}


@app.delete("/api/settings/keys/{provider}")
def delete_api_key(provider: Literal["gemini", "claude"]):
    deleted = api_keys.delete_api_key(provider)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"저장된 {provider} 키가 없습니다")
    return {"provider": provider, "action": "deleted"}


# 연구 워크플로우(⑥) 세션 목록 — 챗 사이드바와 같은 패턴(thread_id는 프론트가 새 연구를
# 시작할 때 uuid4()로 발급, chat.py의 st.session_state.thread_id 발급 방식 그대로).
# /research/sessions처럼 리터럴 경로를 /research/{thread_id} 계열보다 먼저 선언해야
# 한다 — Starlette은 등록 순서대로 매칭하므로, {thread_id}가 먼저 있으면 "sessions"가
# 그 파라미터로 먹혀버린다.
@app.get("/api/research/sessions")
def list_research_sessions():
    return {"sessions": research_sessions.list_sessions()}


class ResearchSessionTitleUpdate(BaseModel):
    title: str


@app.post("/api/research/sessions/{thread_id}/title")
def rename_research_session(thread_id: str, body: ResearchSessionTitleUpdate):
    updated = research_sessions.update_title(thread_id, body.title)
    if not updated:
        raise HTTPException(status_code=404, detail=f"연구 세션 thread_id={thread_id}를 찾을 수 없습니다")
    return {"thread_id": thread_id, "action": "updated"}


# 세션 목록에서만 지운다 — 실제 체크포인트는 안 지운다(research_sessions.delete_session()
# docstring, RoadMap §4 참고).
@app.delete("/api/research/sessions/{thread_id}")
def close_research_session(thread_id: str):
    deleted = research_sessions.delete_session(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"연구 세션 thread_id={thread_id}를 찾을 수 없습니다")
    return {"thread_id": thread_id, "action": "deleted"}


# 워크플로우 본체 호출 — equipment.py의 "None=명시 안 함" 패턴처럼 topic·experiment_results는
# 옵셔널로 받아 넘긴 것만 ainvoke에 실어 보낸다(topic은 최초 hypothesis 호출에만,
# experiment_results는 operation 호출에만 실제로 쓰인다 — WorkflowState 필드 주석 참고).
# 이 thread_id로 research_sessions에 행이 없으면(=신규 연구) 같이 생성한다 — RoadMap
# "새 연구 시작 = 테이블에 새 행 + graph를 ainvoke" 설계 그대로.
class ResearchAdvanceRequest(BaseModel):
    stage: Literal["hypothesis", "design", "operation", "report", "writing"]
    topic: str | None = None
    experiment_results: str | None = None
    # 재생성 시 방향 지시 + 직접 수정한 필드 내용(프론트가 조립해서 하나의 텍스트로
    # 보냄, 08-04 후속 — RoadMap "재생성 시 사용자 피드백/지시 반영") — generate_hypothesis/
    # design_experiment/analyze_results만 읽는다(WorkflowState.user_guidance 필드 참고).
    user_guidance: str | None = None
    # 과거 체크포인트에서 이어갈 때만 쓰는 필드(체크포인트 히스토리·복원, 08-04 후속) —
    # from_checkpoint_id가 있으면 그 시점 값을 현재 tip으로 복원한 뒤 이 요청의 stage로
    # 이어간다. references만은 예외로 항상 최신을 원칙으로 하되(RoadMap 설계 노트 참고),
    # 그 시점 이후 새로 쌓인 것 중 사용자가 명시적으로 남기기로 고른 paper_id만 같이 살린다
    # — 기본값(빈 리스트)은 "그 시점에 없던 참고문헌은 버린다"는 뜻.
    from_checkpoint_id: str | None = None
    keep_reference_paper_ids: list[str] = Field(default_factory=list)


@app.post("/api/research/{thread_id}/advance")
async def advance_research(request: Request, thread_id: str, body: ResearchAdvanceRequest):
    session = research_sessions.get_session(thread_id)
    if session is None:
        # 신규 thread — WorkflowState.topic이 필수 필드라 체크포인트가 없는 첫 호출은
        # topic 없이는 애초에 그래프가 Pydantic 검증에서 터진다. stage도 hypothesis가
        # 아니면(예: 첫 호출인데 design) 가설 없이 설계를 뽑는 이상한 상태가 되므로 막는다.
        if body.topic is None or body.stage != "hypothesis":
            raise HTTPException(
                status_code=400,
                detail="새 연구 세션은 stage='hypothesis'와 topic이 함께 필요합니다",
            )
        research_sessions.create_session(thread_id, title=body.topic, topic=body.topic, stage=body.stage)

    config = {"configurable": {"thread_id": thread_id}}

    if body.from_checkpoint_id is not None:
        past_config = {"configurable": {"thread_id": thread_id, "checkpoint_id": body.from_checkpoint_id}}
        past_snapshot = await request.app.state.research_graph.aget_state(past_config)
        if not past_snapshot.values:
            raise HTTPException(status_code=404, detail=f"checkpoint_id={body.from_checkpoint_id}를 찾을 수 없습니다")
        tip_snapshot = await request.app.state.research_graph.aget_state(config)

        past_references = past_snapshot.values.get("references", [])
        past_paper_ids = {r["paper_id"] for r in past_references}
        keep_ids = set(body.keep_reference_paper_ids)
        kept_new_references = [
            r for r in tip_snapshot.values.get("references", [])
            if r["paper_id"] not in past_paper_ids and r["paper_id"] in keep_ids
        ]
        # 과거 값 전체를 새 tip으로 복사(LLM 호출 없음, main.py의 disabled_models 갱신과
        # 같은 as_node="__start__" 패턴) — 복사 직전까지의 tip은 그 자체로 이미 하나의
        # 체크포인트라 사라지지 않는다, 그쪽으로도 언제든 다시 이 방식으로 돌아올 수 있다.
        await request.app.state.research_graph.aupdate_state(
            config, {**past_snapshot.values, "references": past_references + kept_new_references},
            as_node="__start__",
        )

    inputs = {"stage": body.stage}
    if body.topic is not None:
        inputs["topic"] = body.topic
    if body.experiment_results is not None:
        inputs["experiment_results"] = body.experiment_results
    if body.user_guidance is not None:
        inputs["user_guidance"] = body.user_guidance

    result = await request.app.state.research_graph.ainvoke(inputs, config=config)
    research_sessions.update_stage(thread_id, body.stage)

    # 복원 경로였다면 이 턴이 어느 과거 체크포인트에서 갈라졌는지 기록 — parent_config로는
    # 못 얻는 이유는 research_branches.py 모듈 주석 참고. tip을 다시 조회해야
    # ainvoke가 실제로 남긴 turn-final 체크포인트의 checkpoint_id를 얻는다(ainvoke
    # 반환값은 값 dict일 뿐 체크포인트 메타를 안 담음).
    if body.from_checkpoint_id is not None:
        new_tip = await request.app.state.research_graph.aget_state(config)
        research_branches.record_branch(
            child_checkpoint_id=new_tip.config["configurable"]["checkpoint_id"],
            source_checkpoint_id=body.from_checkpoint_id,
            thread_id=thread_id,
        )

    return result


# 페이지 새로고침 시 재실행 없이 현재 값만 보는 조회 — GET /interests/draft가
# aget_state()로 조회만 하는 것과 같은 패턴. 체크포인트가 아예 없으면(닫힌 적 없는데도
# 한 번도 advance가 안 된 thread_id) snapshot.values가 비어 404.
@app.get("/api/research/{thread_id}")
async def get_research_state(request: Request, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await request.app.state.research_graph.aget_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"연구 세션 thread_id={thread_id}의 상태가 없습니다")
    return snapshot.values


# 체크포인트 히스토리(08-04 후속, "탭처럼 왔다갔다") — 그래프가 노드 하나 실행할 때마다
# 체크포인트를 남겨서(가설 호출 하나에도 generate_hypothesis·find_hypothesis_references
# 두 번) 전부 보여주면 노이즈가 많다. snapshot.next가 빈 튜플인 것만 그 turn(advance
# 호출 하나)의 최종 결과라 그것만 추린다.
#
# 예외 하나: aupdate_state로 값만 주입한 체크포인트(예: /draft의 순수 편집 저장,
# 노드를 안 태우니 LLM 재호출이 없다)는 next가 안 비어있다(실제로 toy 그래프로 재현·확인—
# "다음에 route_by_stage가 이 stage를 다시 라우팅하면 실행될 노드"가 next에 남아서다).
# 그래서 metadata["source"] == "update"인 것도 **가장 최신 것 하나에 한해** 포함한다 —
# 최신이 아닌 update 체크포인트는 항상 그 직후에 실제 advance(loop)가 뒤따라와 already
# next==()로 다시 잡히므로(복원 흐름이 aupdate_state 직후 꼭 ainvoke를 부르는 것과 같은
# 이유) 제외해도 정보 손실이 없다.
# 새로 진행 순(오래된 것부터)으로 뒤집어 반환 — 화면이 타임라인처럼 왼쪽부터 그리기 편하도록.
@app.get("/api/research/{thread_id}/history")
async def get_research_history(request: Request, thread_id: str):
    snapshots = [
        s async for s in request.app.state.research_graph.aget_state_history(
            {"configurable": {"thread_id": thread_id}}
        )
    ]
    entries = []
    for i, snapshot in enumerate(snapshots):
        is_turn_final = not snapshot.next
        is_latest_edit = i == 0 and snapshot.metadata.get("source") == "update"
        if not (is_turn_final or is_latest_edit):
            continue
        entries.append({
            "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"],
            "stage": snapshot.values.get("stage"),
            "created_at": snapshot.created_at,
            "values": snapshot.values,
        })
    entries.reverse()

    # 브랜치형 타임라인(설계 노트 참고)의 세로선(계보) 연결용 — LangGraph 체크포인터의
    # parent_config는 항상 선형이라 못 쓰고(research_branches.py 주석 참고), 복원이
    # 일어날 때 main.py가 따로 남겨둔 기록을 여기서 붙여준다. 분기 없이 만들어진
    # 체크포인트는 매핑에 없으니 None.
    sources = research_branches.get_sources([e["checkpoint_id"] for e in entries])
    # 단계별 메모(08-04 후속, RoadMap "타임라인·체크 결합(브랜치형)" 설계 노트 §단계별
    # 메모, 방식 B) — 체크포인트를 안 건드리는 별도 사이드테이블이라 여기서 같은
    # 방식(N+1 쿼리 없이 한 번에)으로 붙여준다. 메모 없으면 빈 문자열.
    notes = research_notes.get_notes_for_checkpoints([e["checkpoint_id"] for e in entries])
    for entry in entries:
        entry["branched_from_checkpoint_id"] = sources.get(entry["checkpoint_id"])
        entry["note"] = notes.get(entry["checkpoint_id"], "")

    return {"history": entries}


# 단계별 메모(08-04 후속, RoadMap "타임라인·체크 결합(브랜치형)" 설계 노트 §단계별
# 메모, 방식 B로 결정) — 체크포인트를 안 건드리는 별도 사이드테이블(research_notes.py)
# 이라 tip뿐 아니라 과거 체크포인트에도 자유롭게 필기·수정할 수 있다. 그래프를 전혀
# 안 태우고 순수 CRUD라 aget_state/aupdate_state도 필요 없다 — thread_id는 저장할 때
# 같이 남겨두기만 하고(조회는 checkpoint_id 기준), checkpoint_id가 실제로 이 thread의
# 것인지는 검증하지 않는다(프론트가 /history에서 받은 checkpoint_id만 넘기므로).
class ResearchNoteUpdate(BaseModel):
    note: str


@app.post("/api/research/{thread_id}/notes/{checkpoint_id}")
async def save_research_note(thread_id: str, checkpoint_id: str, body: ResearchNoteUpdate):
    research_notes.set_note(checkpoint_id, thread_id, body.note)
    return {"checkpoint_id": checkpoint_id, "note": body.note}


# 논문 초안 인앱 편집(08-04 후속) — draft_paper()가 채우는 텍스트 필드만 대상. PDF가
# 아니라 평범한 문자열이라 편집 자체는 단순하다. equipment.py의 "None=명시 안 함" 패턴
# 그대로 옵셔널 필드만 받아 넘긴 것만 바꾼다. LLM 재호출 없이 aupdate_state로 값만
# 덮어쓴다(복원 기능과 같은 패턴) — 저장 한 번이 새 tip 체크포인트 하나(위 히스토리의
# "가장 최신 update" 예외로 탭에도 잡힘).
class ResearchDraftUpdate(BaseModel):
    title: str | None = None
    abstract: str | None = None
    introduction: str | None = None
    methods: str | None = None
    results: str | None = None
    discussion: str | None = None


@app.post("/api/research/{thread_id}/draft")
async def update_research_draft(request: Request, thread_id: str, body: ResearchDraftUpdate):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await request.app.state.research_graph.aget_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"연구 세션 thread_id={thread_id}의 상태가 없습니다")
    if snapshot.values.get("stage") != "writing":
        raise HTTPException(status_code=400, detail="논문 초안(writing) 단계에서만 수정할 수 있습니다")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await request.app.state.research_graph.aupdate_state(config, updates, as_node="__start__")
        snapshot = await request.app.state.research_graph.aget_state(config)
    return snapshot.values


# 참고문헌만 독립 재시도(08-04 후속, Part B — RoadMap "참고문헌만 재검색 + 실패 사유
# 표시") — 지금까진 "참고문헌을 찾지 못했습니다"가 뜨면 그 단계 전체(가설·설계 등,
# LLM 재호출 포함)를 재생성해야만 참고문헌도 다시 찾아졌다. 이 엔드포인트는 그래프를
# 안 타고 tip의 stage에 맞는 참고문헌 노드 함수만 직접 불러(research_workflow의
# REFERENCE_NODE_BY_STAGE) /draft와 같은 aupdate_state(as_node="__start__") 패턴으로
# 결과만 tip에 얹는다 — 가설·설계 산출물 자체는 안 건드리고 참고문헌 검색(검색어 추출+
# 스크리닝)만 다시 돈다. 노드 함수가 동기(LLM 호출 포함)라 /interests/draft와 같은
# 이유로 asyncio.to_thread로 감싼다.
@app.post("/api/research/{thread_id}/references/retry")
async def retry_research_references(request: Request, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await request.app.state.research_graph.aget_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"연구 세션 thread_id={thread_id}의 상태가 없습니다")

    stage = snapshot.values.get("stage")
    node = research_workflow.REFERENCE_NODE_BY_STAGE.get(stage)
    if node is None:
        raise HTTPException(status_code=400, detail=f"{stage} 단계는 참고문헌 재검색 대상이 아닙니다")

    state = research_workflow.WorkflowState(**snapshot.values)
    updates = await asyncio.to_thread(node, state)
    await request.app.state.research_graph.aupdate_state(config, updates, as_node="__start__")

    new_snapshot = await request.app.state.research_graph.aget_state(config)
    return new_snapshot.values


# 설치판 정적 파일 서빙(08-05, Docker 패키징 착수 — RoadMap "설치 앱의 UI 실행 방식"
# 설계 노트 참고) — 프론트 빌드 산출물을 백엔드가 같은 포트(8000)로 같이 서빙해서
# BACKEND_URL이 빈 문자열(같은 오리진)로 동작하게 한다. 개발 환경(Vite 5173 + 백엔드
# 8000, 서로 다른 포트)에서는 frontend-react/dist가 최신이 아니거나 없을 수 있어
# is_dir()로 감싸 안전하게 건너뛴다 — 이 블록이 없어도 개발 환경은 그대로 동작한다.
# **반드시 파일 맨 끝에 둔다**: 아래 catch-all 라우트(`/{full_path:path}`)가 위의 모든
# API 라우트보다 먼저 등록되면 그것들을 전부 가려버린다(Starlette은 라우트를 등록
# 순서대로 매칭). CORS 미들웨어는 그대로 둔다 — 같은 오리진 요청엔 CORS 헤더가
# 아무 영향이 없어(브라우저가 same-origin 요청엔 CORS 검사 자체를 안 함) 프로덕션에서
# 무해하고, 개발 환경(서로 다른 포트)은 여전히 CORS가 필요하므로 제거하면 그쪽이 깨진다.
FRONTEND_DIST = Path(__file__).parent / "frontend-react" / "dist"

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # 정적 파일이 직접 요청되면(예: /favicon.ico, /manifest.json) 그 파일을 그대로
        # 돌려주고, 그 외(React Router가 처리할 경로, 예: /research)는 index.html을 돌려줘
        # 클라이언트 라우팅이 이어받게 한다 — 새로고침·직접 URL 접근 시 필요한 SPA 폴백.
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
