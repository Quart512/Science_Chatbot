import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from orchestrator import app as app_graph
from typing import Literal
from pydantic import Field
from uuid import uuid4

# fastapi
app = FastAPI()

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
@app.post("/query")
async def query(request: Query):
    config = {"configurable": {"thread_id": request.thread_id}}
    inputs = {"question": request.prompt, "model": request.model, "effort": request.effort}

    async def event_stream():
        async for chunk in app_graph.astream(inputs, config=config, stream_mode="custom"):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")