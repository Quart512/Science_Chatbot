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



# 관심사 목록 조회(08-11②, 라이브러리 표면 "관심사 탭"의 카드 목록) — 지금까지 관심사
# 생성(POST)만 API로 열려있고 조회는 없었다. interests.list_interests()를 그대로
# relay — 판정도 가공도 없는 단순 조회라 /interests 생성 핸들러와 같은 이유로 평범한 def.
@app.get("/interests")
def list_interests():
    return {"interests": interests.list_interests()}


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


# 관심사 삭제(08-11③ 후속, 라이브러리 표면 "관심사 탭"의 카드별 삭제 버튼) — 지금까지
# 생성·수정·조회만 있고 삭제가 없었다. interest_paper 조인 테이블이 아직 없어(RoadMap
# "관심사↔논문이 다대다다" 열린 질문) 이 관심사가 추천한 카탈로그 행을 같이 지우거나
# 남기는 정책은 그 테이블이 생길 때 다시 정한다 — 지금은 interests 테이블 행 하나만
# 지운다. /interests와 같은 이유로 평범한 def.
@app.delete("/interests/{interest_id}")
def delete_interest(interest_id: int):
    deleted = interests.delete_interest(interest_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"관심사 id={interest_id}를 찾을 수 없습니다")
    return {"interest_id": interest_id, "action": "deleted"}


# 추천 검색 트리거(08-09③ 호출 경로, 07-31) — "관심사에서 트리거할 때만" 실행한다는
# 로드맵 원칙 그대로: cron 배치가 아니라 사용자가 라이브러리 관심사 카드에서 "지금 검색"을
# 누를 때만 이 엔드포인트가 불린다. paper_recommend.recommend_for_interest()가 검색(2~3초
# 내외 네트워크 호출)과 후보마다 LLM 스크리닝을 순차로 도는 동안 요청이 몇 초 걸릴 수
# 있는데, 지금은 결과를 한 번에 돌려주는 단순한 형태로 시작한다(단순 경로부터) — 진행
# 상황을 스트리밍하고 싶어지면 그때 /query처럼 SSE로 바꾼다. /interests와 같은 이유로
# 평범한 def(스레드풀 실행, 이벤트 루프 안 막음).
#
# start(08-11①, "추가 검색") — 쿼리 파라미터로 페이지네이션 오프셋을 받는다. 프론트가
# 지금까지 받은 후보 수를 그대로 넘기면 다음 순위부터 이어서 검색·스크리닝한다.
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


# 관심사 수정 직후 자동 재검색(08-11②) — "관심사에서 트리거할 때만" 원칙은 그대로:
# cron이 아니라 프론트가 수정 저장 직후 사용자 행동의 연장으로 호출한다. /search와
# 다른 점은 처음부터 새로 찾는 게 아니라 프론트가 세션에 쌓아둔 기존 후보 목록을
# 같이 넘겨받아 paper_recommend.refresh_for_interest()가 재스크리닝+병합까지 한다
# (그 함수 docstring 참고).
@app.post("/interests/{interest_id}/refresh")
def refresh_recommend_search(interest_id: int, body: RefreshRequest):
    try:
        results = paper_recommend.refresh_for_interest(interest_id, body.existing_candidates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"recommended": results}


# 논문 등록(08-11①, 라이브러리 표면 "논문 탭"의 등록 주 경로) — register_paper()가
# 지금까지 paper/paper_ingest.py의 __main__ 스모크 테스트로만 호출되던 걸 여기서 처음
# API로 노출한다.
#
# multipart/form-data로 파일을 받는다 — register_paper()가 pdf_path(디스크 경로)를 받는
# 시그니처라 업로드 바이트를 임시 파일에 한 번 써서 그 경로를 넘긴다(register_paper()
# 자체를 bytes 인자로 바꾸는 건 이 엔드포인트 하나만을 위한 리팩터링이라 범위 밖).
#
# fitz.FileDataError(PyMuPDF가 유효한 PDF가 아니라고 판단할 때)는 사용자 입력 검증
# 경계에서 나는 에러라 500이 아니라 400으로 변환한다 — 지금까지 register_paper()의
# 유일한 호출자(CLI 스모크 테스트)는 항상 진짜 PDF를 줬으니 이 실패 모드를 신경 쓸
# 필요가 없었지만, API로 노출되는 순간 신뢰 못 할 입력이 된다.
#
# /interests와 같은 이유로 평범한 def — register_paper()는 PDF 파싱(CPU)+임베딩(로컬
# 모델 추론)까지 동기로 도는 무거운 호출이라 이벤트 루프에서 직접 돌리면 안 된다.
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


# 논문 카탈로그 조회(08-11③, 라이브러리 표면 "관심사 탭"의 보유/추천 목록) — status로
# 필터링하되(recommended/owned/dismissed), 관심사별 필터는 아직 없다: paper_catalog에
# interest_id 연결이 없어(RoadMap "관심사↔논문이 다대다다" 열린 질문 — interest_paper
# 조인 테이블 미구현) 지금은 전역 목록만 가능하다. paper_catalog.list_papers()를 그대로
# relay — 판정 없는 단순 조회라 /interests 조회와 같은 이유로 평범한 def.
@app.get("/papers")
def list_papers(status: Literal["recommended", "owned", "dismissed"] | None = None):
    return {"papers": paper_catalog.list_papers(status=status)}
