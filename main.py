from fastapi import FastAPI
from pydantic import BaseModel
from graph import app as app_graph
from typing import Literal

# fastapi
app = FastAPI()

class Query(BaseModel):
    prompt: str
    top_k: int = 3
    limit: int = 4
    model: Literal["gemini", "claude", "Qwen-tuned"] = "gemini"

@app.post("/query")
def query(request: Query):
    app_result = app_graph.invoke({"question": request.prompt, 
                                        "top_k": request.top_k,
                                        "limit": request.limit,
                                        "model": request.model
                                        })
    return {"answer": app_result["answer"], 
            "comment" : app_result["comment"]}