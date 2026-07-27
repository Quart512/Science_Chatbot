from fastapi import FastAPI
from pydantic import BaseModel
from orchestrator import app as app_graph
from typing import Literal
from pydantic import Field
from uuid import uuid4

# fastapi
app = FastAPI()

# top_k/limit은 물리 QA 능력 내부 다이얼이라 ParentState엔 없음 — 지금은 능력이 하나뿐이라
# orchestrator.physics_qa_node의 기본값(top_k=3, limit=4)을 그대로 씀. 능력별 파라미터를
# API 레벨에서 다시 노출하고 싶어지면(예: 라우터가 여러 능력을 부를 때) 그때 재설계.
class Query(BaseModel):
    prompt: str
    model: Literal["gemini", "claude", "Qwen-tuned"] = "gemini"
    thread_id: str = Field(default_factory=lambda: str(uuid4()))

@app.post("/query")
def query(request: Query):
    app_result = app_graph.invoke({"question": request.prompt,
                                        "model": request.model},
                                        config={"configurable": {"thread_id": request.thread_id}
                                        })
    return {"answer": app_result["answer"],
            "comment" : app_result["comment"]}