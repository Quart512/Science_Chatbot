from fastapi import FastAPI
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

@app.post("/query")
def query(request: Query):
    app_result = app_graph.invoke({"question": request.prompt,
                                        "model": request.model,
                                        "effort": request.effort},
                                        config={"configurable": {"thread_id": request.thread_id}
                                        })
    return {"answer": app_result["answer"],
            "comment" : app_result["comment"]}