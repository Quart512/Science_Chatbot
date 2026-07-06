Thank you to arXiv for use of its open access interoperability.

## 개요

7주차 LangChain RAG를 LangGraph `StateGraph`로 마이그레이션하고, verify 루프를 추가해 AI Agent로 확장. FastAPI로 REST API 래핑.

## 파일 구조

```
08/
├── docs/
│   └── feynman.txt       # 파인만 강의록
├── chroma_db/            # ChromaDB 영구 저장소 (06에서 복사)
├── ingest.py             # 인덱싱: 청킹 → 임베딩 → ChromaDB 저장
├── graph.py              # LangGraph StateGraph: retrieve → generate → verify 루프 (needs_more_context 시 retrieve 재진입)
├── main.py               # FastAPI 래핑: POST /query
└── .env                  # GOOGLE_API_KEY 등 (git 제외)
```

## 그래프 구조

```
START → retrieve → generate → verify →─── fix_needed=False ──→ final_answer → END
                      ↑                ├── fix_needed=True, needs_more_context=False → generate (루프)
                      └────────────────┘── fix_needed=True, needs_more_context=True  → retrieve (top_k+1)
```

- **retrieve**: 질문을 벡터 검색해 관련 문서 반환 (기본 top_k=3). `needs_more_context=True`로 재진입 시 top_k를 1 늘려 재검색
- **generate**: `bind_tools()`로 LLM에 tool 목록 전달 → LLM이 DuckDuckGo/Wikipedia/ArXiv 중 필요한 것 선택 → 결과를 Document로 변환해 RAG context에 합쳐 답변 생성. fix 브랜치에서는 `what_to_fix`도 프롬프트에 반영
- **verify**: Pydantic 구조화 출력으로 `fix_needed`, `what_to_fix`, `needs_more_context` 판단
- **route_by_fix**: verify 결과에 따라 3방향 분기 — `final_answer` / `generate` 재실행 / `retrieve` 재진입. `try_count >= limit(4)` 시 강제 종료

## 07 LCEL vs 08 LangGraph 비교

| 항목 | 07 LCEL | 08 LangGraph |
|---|---|---|
| 구조 | 선형 파이프 (`\|`) | 노드 + 엣지 그래프 |
| 루프 | 불가 (DAG) | 가능 (사이클 허용) |
| 상태 관리 | 없음 | `TypedDict` State |
| 조건 분기 | `RunnableBranch` | `add_conditional_edges` |
| 에이전트 패턴 | 어려움 | 자연스럽게 구현 가능 |

## 실행

```bash
# 서버
uv run fastapi dev main.py

# 단독 실행 (터미널 테스트)
uv run graph.py
```

## API

```
POST /query
{
  "prompt": "파인만이 설명한 원자가 뭐야?",
  "top_k": 3,
  "limit": 4,
  "model": "gemini"
}

→ {"answer": "..."}
```

- `model`: `"gemini"` (기본값) 또는 `"claude"`
- `top_k`: 검색 문서 수 (기본값 3)
- `limit`: 최대 루프 횟수 (기본값 4)

## 환경변수 (.env)

```
GOOGLE_API_KEY=...
```

## 사용 라이브러리

- `langgraph` — StateGraph, 노드/엣지, 조건 분기
- `langchain-google-genai` — Gemini 임베딩 + LLM
- `langchain-chroma` — ChromaDB 연동
- `langchain-core` — 프롬프트 템플릿, StrOutputParser
- `pydantic` — 구조화 출력 스키마
- `fastapi` + `uvicorn` — REST API
- `python-dotenv` — API 키 관리
- `langchain-anthropic` — Claude LLM 연동
- `langchain-community` — DuckDuckGoSearchRun, WikipediaQueryRun, ArxivQueryRun
- `duckduckgo-search` — DuckDuckGo 검색 백엔드
- `wikipedia` — Wikipedia API 백엔드
- `arxiv` — ArXiv API 백엔드
