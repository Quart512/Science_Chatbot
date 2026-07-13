# Science Chatbot — 물리 연구 어시스턴트

실험을 보조하고, 논문을 검색·학습해 지식을 안내하는 과학 챗봇. 최종 목표는 오케스트레이터가 전문 에이전트들을 라우팅하는 **멀티 에이전트 물리 연구 어시스턴트**이며, 현재는 그 첫 구성 요소인 **Self-RAG 스타일 단일 에이전트**(물리 지식 에이전트)가 동작한다.

## 목표 아키텍처

![멀티 에이전트 아키텍처](docs/architecture.png)

| 에이전트 | 역할 | 핵심 기법 |
|---|---|---|
| 오케스트레이터 | 의도 분류·라우팅·응답 조립 | Supervisor 패턴 |
| 물리 지식 | 물리 법칙 설명 | RAG ← **현재 구현** |
| 문헌 학습·평가 | 논문 요약·신뢰도 평가 → 장기기억 승격 | Evaluator-Optimizer |
| 가설 수립 | 검증 가능한 가설 생성 | - |
| 실험 설계 (서브) | 가설 → 실험 프로토콜 (변수·통제조건·장비) | Plan-and-Execute |
| 실험 운영 | 도구·자원 점검, 진행 추적, 결과 분석 → 재설계 요청 | - |
| 논문 작성 | 결과 종합, 초안 작성 | - |
| 논문 조달 | 논문 탐색·트리아지, 구매는 사람이 결정 | Human-in-the-loop |
| 번역 레이어 | 응답 직전 한국어 후처리 (원문 병기) | - |

설계 원칙: 실험 안전은 공유 가드레일이 계획·실행 양 단계에서 검사하고 임계치 초과 시 사람 승인 전까지 진행 불가. 멀티 에이전트 전환은 재작성이 아니라 현재 그래프를 서브그래프로 포장하는 방식.

## 현재 구현 — Self-RAG 에이전트

```
START → retrieve → generate ──(tool 요청)──→ run_tools ──→ generate (ReAct 루프)
             ↑          └─(답변 완성)→ verify ──── 통과 ────→ final_answer → END
             │                          ├── 수정 필요 → generate (재시도)
             └──────────────────────────┘── 컨텍스트 부족 → retrieve (top_k+1)
```

- **retrieve**: 벡터 검색 (기본 top_k=3). 재검색 시 벡터DB 문서는 교체하되 tool로 수집한 증거는 보존
- **generate**: 대화 이력(`add_messages` reducer) 기반 답변 생성. tool이 필요하면 `tool_calls`만 요청 — 실행은 run_tools 노드 담당. 재시도 시 verify의 지적사항을 대화 메시지로 반영
- **run_tools**: tool 실행 + 예외처리. 모든 tool_call에 반드시 ToolMessage로 응답(실패 포함) → LLM이 다음 라운드에 에러를 읽고 자가수정. 빈 결과·호출 실패·미등록 tool을 구분해 다른 힌트 제공, **연속 2회 실패한 tool은 해당 런에서 자동 제외(서킷 브레이커)**. 성공 결과는 Document로 변환해 RAG context에 병합
- **verify**: 구조화 출력(`fix_needed`, `what_to_fix`, `needs_more_context`)으로 답변 검증. **생성 모델과 다른 모델이 검증** (교차 검증)
- **route_by_fix**: 3방향 분기. `try_count >= limit` 시 강제 종료 + 실패 사유 명시
- **State**: Pydantic 모델 — 필드 기본값·타입 검증, `messages`는 `add_messages` reducer로 자동 누적

### 특징

- **모델 선택 + fallback 체인**: `model_map`(gemini-2.5-flash / claude-haiku)에서 요청별 선택, rate limit 등 오류 시 남은 모델로 자동 전환. 모델 추가는 항목 한 줄 — 추후 개인 언어 모델(vLLM/Ollama, OpenAI 호환 API)도 같은 방식으로 연동 예정
- **로컬 임베딩** (BAAI/bge-m3): 임베딩에 API rate limit·비용 없음, 검색 시 외부 의존 없음
- **LangSmith tracing** + LLM-as-judge 평가 (`evaluate.py`, `docs/eval.json` 31문항 — 미해결 문제 포함)

## 파일 구조

```
Science_Chatbot/
├── docs/
│   ├── architecture.png     # 목표 아키텍처 다이어그램
│   ├── feynman.txt          # 코퍼스: The Feynman Lectures on Physics
│   ├── README_08.md         # 개발 회고 (주차별)
│   ├── eval.json            # 평가 데이터셋 (질문/정답/카테고리/난이도/unsolved)
│   ├── eval.md               # eval.json에서 자동 생성되는 카테고리별 표
│   └── generate_eval_md.py  # eval.json → eval.md 생성 스크립트
├── chroma_db/            # ChromaDB 영구 저장소
├── ingest.py             # 인덱싱: 청킹 → 로컬 임베딩 → ChromaDB
├── graph.py              # LangGraph StateGraph (에이전트 본체)
├── main.py               # FastAPI: POST /query
├── evaluate.py           # docs/eval.json 로드 → LLM-as-judge 평가 (unsolved 문항 별도 채점)
└── .env                  # API 키 (git 제외)
```

## 실행

```bash
# 의존성 설치
uv sync

# 인덱싱 (최초 1회)
uv run ingest.py

# 서버
uv run fastapi dev main.py

# 단독 실행 (터미널 테스트)
uv run graph.py
```

> **임베딩 모델 참고**: `BAAI/bge-m3`는 별도 설치가 필요 없다 — 첫 실행 시 Hugging Face Hub에서 자동 다운로드된다 (약 2GB, `~/.cache/huggingface`에 캐시). 이후 실행은 캐시를 사용하므로 빠르며, API 키·네트워크 없이 로컬에서 동작한다. 단 `ingest.py`와 `graph.py`는 반드시 같은 임베딩 모델을 써야 한다 (모델이 다르면 벡터 공간이 달라져 유사도 검색이 무의미해짐).

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
- `limit`: 최대 verify 루프 횟수 (기본값 4)

## 환경변수 (.env)

```
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...
LANGSMITH_API_KEY=...   # 선택: tracing·평가용
```

## 로드맵

1. Pydantic State 전환 + `messages`(add_messages) 필드 — 기반 리팩토링
2. tool 노드 분리 (ReAct 표준 구조) → `interrupt_before`로 human-in-the-loop
3. 단기기억 + 쓰레드 (checkpointer, thread_id별 세션)
4. 프론트엔드 (Streamlit)
5. 멀티 에이전트 전환: 현 그래프를 물리 지식 에이전트로 포장 → 오케스트레이터 → 문헌·조달·가설·실험 설계·번역 레이어
6. 장기기억 유저별 분리 (VDB 메타데이터 필터링)
7. 실험: verify 구성 비교 (self / 교차 / 무 verify / 다중 모델 앙상블 — correctness·토큰·지연 지표)
8. 개인 언어 모델 연동 및 비교 평가 (vs 가중치 공개 모델 vs 프론티어 모델)

## 데이터 & 감사

- 코퍼스: [The Feynman Lectures on Physics](https://www.feynmanlectures.caltech.edu/) — Caltech이 무료 공개한 파인만의 물리학 강의록
- Thank you to arXiv for use of its open access interoperability.

## 사용 라이브러리

- `langgraph` — StateGraph, 조건 분기, (예정) checkpointer·interrupt
- `langchain-google-genai` / `langchain-anthropic` — LLM
- `langchain-huggingface` — 로컬 임베딩 (bge-m3)
- `langchain-chroma` — 벡터 저장소
- `langchain-community` + `ddgs` — 웹 검색 tool
- `pydantic` — 구조화 출력·State 스키마
- `fastapi` + `uvicorn` — REST API
- `langsmith` — tracing·평가
