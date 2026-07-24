# Science Chatbot — 물리 연구 어시스턴트

실험을 보조하고, 논문을 검색·학습해 지식을 안내하는 과학 챗봇. 최종 목표는 오케스트레이터가 전문 에이전트들을 라우팅하는 **멀티 에이전트 물리 연구 어시스턴트**이며, 현재는 그 첫 구성 요소인 **Self-RAG 스타일 단일 에이전트**(물리 지식 에이전트)가 동작한다.

## 문서 안내

역할별로 문서를 나눠 뒀다. 무엇을 고칠 때 어디를 보면 되는지:

| 문서 | 담는 내용 | 업데이트 시점 |
|---|---|---|
| **README.md** (이 문서) | 현황 — 무엇인가, 아키텍처, 현재 구현, 실행법, API, 평가 | 사실이 바뀔 때만 (API·명령어·구조·아키텍처 변경) |
| **[docs/DEPLOY.md](docs/DEPLOY.md)** | 배포 방법 (빅뱅/Docker 방식 설치·운영 절차) | 배포 절차·환경이 바뀔 때 (README와 함께 움직이는 경우 많음) |
| **[docs/RoadMap.md](docs/RoadMap.md)** | 개발 이력(완료)·진행 중·예정 + 설계 노트·열린 질문·방향성 메모 | 상시 — 진행 상황이 바뀔 때마다 |
| **To Do List** (Obsidian 칸반) | 실행 단위 할 일 | 상시 — RoadMap과 짝으로 동기화 |
| **docs/README_08~11.md** | 주차별 개발 회고 (아카이브) | 해당 주차 마무리 시 1회 |

> 평소엔 **RoadMap ↔ To Do List**만 동기화하면 된다. 완료한 기능이 현황을 바꾸는 순간(예: 프론트엔드 추가 → 실행법 변경)에만 README/DEPLOY도 함께 손본다.

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
| 논문 조달 | 논문 탐색·트리아지 → 추천 리스트 생성 (구매 자체는 에이전트 밖의 일) | 트리아지·랭킹 |
| 번역 레이어 | 응답 직전 한국어 후처리 (원문 병기) | - |

### 설계 포인트

- **가설 수립(③)과 실험 설계(③b) 분리**: 가설을 세우는 일(귀추적 추론)과 그 가설을 검증 가능한 실험으로 번역하는 일(방법론·장비·통제조건 설계)은 성격이 다른 작업이라 서브에이전트로 나눴다. ③은 오케스트레이터가 라우팅하는 진입점, ③b는 ③이 신규 가설을 넘길 때와 ④가 재실험/대체실험을 요청할 때만 내부적으로 호출되는 하위 단계.
- **재실험·대체실험 루프는 ③b만 재호출**: 실험 운영(④)이 재실험이 필요하다고 판단하면 가설 수립(③)은 다시 거치지 않고 ③b에만 재설계를 요청한다. 가설은 고정한 채 실험 프로토콜만 다시 짜는 게 훨씬 흔한 경로이기 때문 — 매번 가설부터 재추론하면 낭비.
- **오케스트레이터 우회 직접 연결**: 문헌 평가 ↔ 물리 지식(정합성 검증), ③b 실험 설계 ↔ 실험 운영(인벤토리 조회·결과 피드백, 양방향)은 오케스트레이터를 거치지 않는다. 매 내부 검증마다 왕복시키면 지연만 늘기 때문.
- **안전 가드레일 (Human-in-the-loop)**: 실험 안전은 각 에이전트가 자체 판단하지 않고, 공유 인프라의 규칙 기반 가드레일을 계획(③b)·실행(④) 양 단계에서 공통 조회. 임계치 초과 시 사람 승인 전까지 진행 불가 — 그래프가 실행 중간에 멈춰 사람 입력을 기다렸다가 재개하는, 실제 `interrupt_before` 기반 HITL이 필요한 지점은 여기뿐이다.
- **논문 조달은 HITL이 아니다**: 논문 조달 에이전트는 순위·근거가 담긴 추천 리스트를 만드는 데서 끝난다. 그 리스트를 보고 실제로 살지 말지는 사람이 시스템 밖에서 결정하고, 산 논문의 PDF를 RAG에 넣는 것도 별도의 수동 ingest 절차다(이미 보유한 논문인지 확인하는 것도 또 다른 기능/DB). 같은 실행 흐름이 멈췄다 재개되는 게 아니라 아예 다른 시점의 별개 작업이라, 엄밀히는 그래프 차원의 HITL 메커니즘이 아니다.
- **진행상황 안내**: 실험 운영 에이전트는 오케스트레이터를 통해 사용자에게 비동기로 실시간 진행상황을 전달한다 (유일하게 오케스트레이터를 통과하는 내부 알림 경로).
- **멀티 에이전트 전환은 재작성이 아니라 포장**: 현재 그래프를 서브그래프로 감싸는 방식 — 컴파일된 그래프를 부모 그래프의 노드로 넣는다.

## 현재 구현 — Self-RAG 에이전트

```
START → reset_turn → retrieve → generate ──(tool 요청)──→ run_tools ──→ generate (ReAct 루프)
                          ↑          └─(답변 완성)→ verify ──── 통과 ────→ final_answer → END
                          │                          ├── 수정 필요 → generate (재시도)
                          └──────────────────────────┘── 컨텍스트 부족 → retrieve (top_k+1)
```

- **reset_turn — 멀티턴 경계**: 매 요청 진입 시 임시 상태(try_count, fix_needed, comment, 서킷 브레이커 등)를 전부 초기화하되 **대화 이력(messages)만 보존** — checkpointer로 살아남은 이전 턴의 잔여 상태가 새 턴을 오염시키지 않게 하는 턴 경계선
- **retrieve**: 벡터 검색 (기본 top_k=3). 재검색 시 벡터DB 문서는 교체하되 tool로 수집한 증거는 보존
- **generate**: 대화 이력(`add_messages` reducer) 기반 답변 생성. tool이 필요하면 `tool_calls`만 요청 — 실행은 run_tools 노드 담당. 재시도 시 verify의 지적사항을 대화 메시지로 반영
- **run_tools**: tool 실행 + 예외처리. 모든 tool_call에 반드시 ToolMessage로 응답(실패 포함) → LLM이 다음 라운드에 에러를 읽고 자가수정. 빈 결과·호출 실패·미등록 tool을 구분해 다른 힌트 제공, **연속 2회 실패한 tool은 해당 런에서 자동 제외(서킷 브레이커)**. 성공 결과는 Document로 변환해 RAG context에 병합
- **verify**: 구조화 출력(`fix_needed`, `what_to_fix`, `needs_more_context`)으로 답변 검증. **생성 모델과 다른 모델이 검증** (교차 검증) — generate가 fallback으로 갈아탄 경우에도 실제 생성 모델(`generated_by`)을 기준으로 회피하며, 가용 모델이 하나도 안 남으면 차순위로 생성자 본인이 검증
- **route_by_fix**: 3방향 분기. `try_count >= limit` 시 강제 종료 + 실패 사유 명시
- **final_answer — 출력 이원화**: `answer`(답변 본문, 평가 대상)와 `comment`(부가 정보, 사용자 전용)를 분리. 재시도를 거친 답변만 structured output으로 본문/메타를 분리하고(평시 추가 호출 0), limit 도달·fallback 발생 같은 시스템 고지는 코드가 comment에 작성 — 실패해도 사용자에게 정직하게 알린다
- **State**: Pydantic 모델 — 필드 기본값·타입 검증, `messages`는 `add_messages` reducer로 자동 누적

### 특징

- **단기기억 (멀티턴 대화)**: `MemorySaver` checkpointer + `thread_id` — 같은 thread_id로 요청하면 대화 이력이 이어져 후속 질문("방금 답을 요약해줘")이 가능. thread_id 미지정 시 uuid가 자동 발급되어 단발 요청도 안전. verify에는 "맥락상 답할 수 없는 모호한 질문에 명확화를 요청한 답변은 정확한 대응" 기준을 추가해 멀티턴 특유의 불완전한 질문에 대응. (MemorySaver는 프로세스 메모리라 서버 재시작 시 소멸 — 영속화는 SqliteSaver로 예정)
- **모델 선택 + fallback 체인**: `model_map`(gemini-2.5-flash / claude-haiku / **Qwen-tuned**)에서 요청별 선택, rate limit·접속 오류 시 남은 모델로 자동 전환. 실패한 모델은 `disabled_models`로 State에 기록되어 같은 요청 안에서는 재시도하지 않음 (노드를 넘나드는 모델 서킷 브레이커). 회피 대상(`models_skip`, 요청마다 새로 정함)과 고장 목록(`disabled_models`, 실패 시 누적)을 별도 파라미터로 분리 — 합쳐서 관리하면 "이번엔 피하고 싶을 뿐"과 "완전히 죽었음"이 뒤섞여 생성자 자신이 영구 배제될 수 있음.

2개 모델이 동시에 장애여도 3번째로 정상 응답 — 상세 로그: [docs/README_09.md](docs/README_09.md#장애-복원력-테스트)
- **자체 파인튜닝 모델 연동**: Qwen2.5-1.5B를 물리 QA로 QLoRA 파인튜닝 → Q4_K_M GGUF → 로컬 llama-server(OpenAI 호환)로 서빙 ([docs/README_09.md](docs/README_09.md) 참고)
- **로컬 임베딩** (BAAI/bge-m3): 임베딩에 API rate limit·비용 없음, 검색 시 외부 의존 없음
- **LangSmith tracing** + LLM-as-judge 평가 (아래 [평가](#평가) 참고)

## 파일 구조

```
Science_Chatbot/
├── docs/
│   ├── architecture.png     # 목표 아키텍처 다이어그램
│   ├── feynman.txt          # 코퍼스: The Feynman Lectures on Physics
│   ├── RoadMap.md           # 개발 이력·계획 (완료/진행중/예정 + 설계 노트)
│   ├── DEPLOY.md            # 배포 가이드 (빅뱅/Docker 방식)
│   ├── README_08.md         # 개발 회고 (8주차: LangGraph 에이전트)
│   ├── README_09.md         # 개발 회고 (9주차: QLoRA 파인튜닝·양자화·GGUF)
│   ├── README_10.md         # 개발 회고 (10주차: 서버 관찰·패킷 캡처)
│   ├── README_11.md         # 개발 회고 (11주차: Docker·EC2·CI/CD)
│   └── train_qa.json        # 파인튜닝 학습 데이터 45문항 (파인만 강의록 기반)
├── tests/
│   ├── conftest.py                  # 공용 설정 — retrieval import-time 로딩 차단, API 키 더미값, make_state fixture
│   ├── test_routing.py              # route_by_fix (순수 라우팅 함수)
│   ├── test_reset_turn.py           # reset_turn (State 초기화 로직)
│   ├── test_tokens.py               # _add_tokens (토큰 누적 헬퍼)
│   └── test_invoke_with_fallback.py # invoke_with_fallback (모델 fallback, model_map 모킹)
├── evaluation/
│   ├── eval.json             # 평가 데이터셋 31문항 (질문/정답/카테고리/난이도/unsolved)
│   ├── eval.md               # eval.json에서 자동 생성되는 카테고리별 표
│   ├── generate_eval_md.py   # eval.json → eval.md 생성 스크립트
│   ├── evaluate.py           # LLM-as-judge 평가 (--target으로 평가 대상 선택)
│   ├── eval_avg.py           # results/의 실행별 평균 점수 요약
│   └── results/               # evaluate.py 실행 결과 (모델별 JSON)
├── models/               # GGUF 모델 가중치 (git 제외)
├── chroma_db/            # ChromaDB 영구 저장소
├── graph.py              # LangGraph StateGraph — 에이전트 본체 (State, 노드, 배선)
├── models.py             # model_map + invoke_with_fallback (모델 등록·fallback 정책의 단일 지점)
├── tool.py               # tool 레지스트리 (검색 tool 팩토리, tools_list, tool_map)
├── retrieval.py          # 임베딩 + 벡터스토어 (ingest와 공유 — 임베딩 모델 불일치를 구조로 방지)
├── ingest.py             # 인덱싱: 청킹 → 로컬 임베딩 → ChromaDB
├── main.py               # FastAPI: POST /query
└── .env                  # API 키 (git 제외)
```

## 사전 준비

| 도구 | 용도 | 설치 |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | 파이썬 버전·패키지 관리 (필수) | `brew install uv` 또는 `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 자체 모델(GGUF) 로컬 서빙 — `Qwen-tuned` 사용 시에만 | `brew install llama.cpp` |

Python은 따로 설치하지 않아도 된다 — `uv sync`가 `pyproject.toml`의 `requires-python`에 맞는 버전을 자동으로 받아온다. 파이썬 패키지 의존성 전체는 `pyproject.toml`에 선언되어 있고 `uv sync` 한 번으로 설치된다. API 키는 아래 [환경변수](#환경변수-env) 참고.

## 실행

> 아래는 로컬 개발용 최소 실행법이다. EC2 등 서버 배포(빅뱅 방식/Docker 방식 둘 다)는 **[docs/DEPLOY.md](docs/DEPLOY.md)** 참고. ⚠️ EC2 인스턴스를 중지 후 재시작하면 퍼블릭 IP가 바뀐다 — GitHub Actions를 쓴다면 `EC2_HOST` Secret도 같이 갱신해야 함(상세: DEPLOY.md 2.7).

```bash
# 의존성 설치
uv sync

# 인덱싱 (최초 1회)
uv run ingest.py

# 서버
uv run fastapi dev main.py

# 단독 실행 (터미널 테스트)
uv run graph.py

# (선택) 자체 파인튜닝 모델 서빙 — model: "Qwen-tuned" 사용 시 필요
llama-server -m models/qwen_finetuned_Q4_K_M.gguf --port 8080
```

> **GGUF 참고**: 모델 가중치(941MB)는 용량 문제로 저장소에 포함되지 않는다 (`models/`는 git 제외). `Qwen-tuned` 없이도 gemini/claude로 모든 기능이 동작하며, 파인튜닝 과정은 [docs/README_09.md](docs/README_09.md)에 기록되어 있다.

> **임베딩 모델 참고**: `BAAI/bge-m3`는 별도 설치가 필요 없다 — 첫 실행 시 Hugging Face Hub에서 자동 다운로드된다 (약 2GB, `~/.cache/huggingface`에 캐시). 이후 실행은 캐시를 사용하므로 빠르며, API 키·네트워크 없이 로컬에서 동작한다. 단 `ingest.py`와 `graph.py`는 반드시 같은 임베딩 모델을 써야 한다 (모델이 다르면 벡터 공간이 달라져 유사도 검색이 무의미해짐).

## 테스트

```bash
uv run pytest
```

실제 LLM 호출·벡터DB·임베딩 모델 없이(모두 모킹 또는 회피) 1~2초 안에 끝나는 유닛 테스트. "노드 내부 구현"이 아니라 "여러 노드가 공유하는 지점"만 골라서 검증한다 — 어떤 노드가 어떻게 바뀌든, 그 지점을 통과하는 입출력이 규격만 지키면 테스트는 그대로 유효하다는 원칙:

- `route_by_fix` — 순수 라우팅 함수 (State만 보고 다음 노드 결정)
- `reset_turn` — State 초기화가 정확한지 + `messages`는 절대 안 건드리는지
- `_add_tokens` — 토큰 누적 헬퍼 (provider가 얹어주는 낯선 키를 무시하는지)
- `invoke_with_fallback` — `model_map`을 통째로 모킹해서, 진짜 API 호출 없이 fallback·서킷 브레이커 로직만 검증

`tests/conftest.py`가 두 가지 import-time 문제를 미리 막아준다: `retrieval.py`의 무거운 임베딩 모델 로딩(가짜 모듈로 대체), `models.py`의 `model_map` 생성 시 API 키 존재 검사(더미 키로 통과, 로컬 `.env` 값은 덮어쓰지 않음). 그래서 CI에도 별도 API 키 Secret 없이 그대로 돈다.

`.github/workflows/deploy.yml`의 `test` job이 이 테스트를 빌드·배포 전에 자동 실행하는 게이트 역할을 한다 — 실패하면 `deploy` job(이미지 빌드+push+EC2 배포)은 시작조차 안 됨. 상세: [docs/README_11.md](docs/README_11.md#8-테스트-게이트).

## API

```
POST /query
{
  "prompt": "파인만이 설명한 원자가 뭐야?",
  "top_k": 3,
  "limit": 4,
  "model": "gemini",
  "thread_id": "user-123"
}

→ {"answer": "...", "comment": "..."}
```

- `model`: `"gemini"` (기본값) / `"claude"` / `"Qwen-tuned"` (로컬 llama-server 필요)
- `top_k`: 검색 문서 수 (기본값 3)
- `limit`: 최대 verify 루프 횟수 (기본값 4)
- `thread_id`: 대화 세션 식별자 — 같은 값으로 요청하면 이전 대화 맥락이 이어짐(단기기억). 생략 시 uuid 자동 발급(맥락 없는 단발 요청)
- 응답의 `answer`는 답변 본문(평가 대상), `comment`는 부가 정보 — 모델의 주의점, limit 도달·fallback 발생 고지 등. 정상 처리 시 comment는 비어 있을 수 있음

## 평가

`evaluation/eval.json` 31문항(7개 물리 카테고리 + 미해결 문제)을 LLM-as-judge로 채점한다. 채점자는 claude-haiku로 **전 실행에서 동일하게 고정** — 채점자가 바뀌면 실행 간 비교가 오염되기 때문. 미해결(unsolved) 문항은 "미해결임을 인정하는가 + 언급한 사실이 정확한가"를 별도 기준으로 채점한다.

```bash
uv run evaluation/evaluate.py --target gemini                              # 모델 단독 (bare)
uv run evaluation/evaluate.py --target claude
uv run evaluation/evaluate.py --target Qwen-tuned --name qwen-tuned-q4     # llama-server 필요
uv run evaluation/evaluate.py --target graph                               # RAG+verify 전체 파이프라인
```

- `--target`: 평가 대상. bare 모델끼리는 모델 역량 비교, graph vs bare는 파이프라인 기여도 비교
- `--name`: 결과 저장 이름 (기본값 target) — 같은 모델의 변형(양자화 전/후 등) 구분용
- 결과는 `evaluation/results/eval_{name}.json`에 저장되어 실행 간 비교 가능
- `uv run evaluation/eval_avg.py`: `evaluation/results/`의 모든 실행 파일별 평균 점수를 한눈에 비교

## 환경변수 (.env)

```
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...
LANGSMITH_API_KEY=...   # 선택: tracing·평가용
```

## 개발 이력 · 로드맵

지금까지의 진행 과정과 앞으로의 계획은 별도 문서에 정리되어 있다:

- **[docs/RoadMap.md](docs/RoadMap.md)** — 날짜별 개발 이력(완료), 진행 중, 예정 전체. 설계 노트·열린 질문·방향성 메모 포함
- **주차별 회고** — [README_08](docs/README_08.md)(LangGraph 에이전트) · [README_09](docs/README_09.md)(QLoRA 파인튜닝·평가) · [README_10](docs/README_10.md)(서버 관찰) · [README_11](docs/README_11.md)(Docker·EC2·CI/CD)

## 데이터 & 감사

- 코퍼스: [The Feynman Lectures on Physics](https://www.feynmanlectures.caltech.edu/) — Caltech이 무료 공개한 파인만의 물리학 강의록. *"I learned very early the difference between knowing the name of something and knowing something."*
- 참고(랭체인 RAG 챗봇): [Notion](https://app.notion.com/p/adapterz/fab394a4806183f78b20013d0fa13dd4?source=copy_link)
- Thank you to arXiv for use of its open access interoperability.

## 사용 라이브러리

- `langgraph` — StateGraph, 조건 분기, (예정) checkpointer·interrupt
- `langchain-google-genai` / `langchain-anthropic` — LLM
- `langchain-openai` — 로컬 llama-server 연결 (OpenAI 호환 클라이언트)
- `langchain-huggingface` — 로컬 임베딩 (bge-m3)
- `langchain-chroma` — 벡터 저장소
- `langchain-community` + `ddgs` — 웹 검색 tool
- `pydantic` — 구조화 출력·State 스키마
- `fastapi` + `uvicorn` — REST API
- `langsmith` — tracing·평가
- `pytest` — 유닛 테스트 (dev 의존성, [테스트](#테스트) 참고)
