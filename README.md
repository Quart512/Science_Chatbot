# Science Chatbot — 물리 연구 어시스턴트

실험을 보조하고, 논문을 검색·학습해 지식을 안내하는 물리 연구 어시스턴트. 최종 목표는 **표면(UI) · 능력(에이전트 그래프) · 데이터 서비스의 3층 구조**이며, 현재는 그 핵심 능력인 **Self-RAG 스타일 물리 QA 에이전트**가 동작한다.

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

> **2026-07-24 개편**: "오케스트레이터 하나가 전문 에이전트들을 라우팅하는 단일 챗봇"에서 **표면 / 능력 / 데이터 3층 구조**로 전환했다. 배경·근거·수정사항은 [docs/README_12.md §7](docs/README_12.md) 참고.

![표면/능력/데이터 3층 아키텍처](docs/architecture.png)

핵심 원칙: **챗봇을 쪼개는 게 아니라, 작업 성격에 맞는 UI 형태를 준다** — 대화는 챗, 추천은 피드, 등록은 폼+어시스트, 연구는 단계형 워크플로우. 상시 챗봇은 메인 챗 하나뿐이고, 나머지 기능은 능력(호출당하는 서브그래프/함수)이나 파이프라인으로 존재한다.

### 표면 — 사용자가 만나는 곳

| 표면 | 형태 | 내용 |
|---|---|---|
| 메인 챗 | 상시 대화형 | 물리 QA(④). 얇은 라우터가 QA / 문서 작성기 호출 / 논문 등록·추천 조회로 분기 (거대 슈퍼바이저 불필요) |
| 연구 워크플로우 | 단계형·HITL | 가설 수립 → 실험 설계 → 실험 운영 → 논문 초안(⑥⑦). 며칠씩 걸리는 상태 있는 작업이라 현 단계가 보이는 별도 화면 |
| 라이브러리 | 관리 UI (탭) | 관심사·논문·실험도구·지식 노트를 등록·조회·관리하는 통합 화면. 관심사 탭: 관심사 카드별 보유/추천/권위 논문 목록 + "지금 검색" 트리거(③). 논문 탭: PDF·DOI·arxiv id 등록 → ② ingest (등록의 주 경로 — 메인 챗 붙여넣기는 보조). 편집은 폼 + AI 어시스트(문서 작성기) |
| 피드 | 뉴스 목록 | **관심사와 무관하게** 현재 hype인 소식을 cron 크롤링 → 키워드 태깅 → 관심사와 일치하는 키워드는 다른 색으로 강조 + 상단 정렬. 추천 검색(③)과는 별개 — 피드는 싸고 넓게, 추천은 비싸고 깊게 |

### 능력 — 호출당하는 그래프/함수 (챗봇 아님)

| 능력 | 역할 | 핵심 기법 | 재사용처 |
|---|---|---|---|
| 물리 QA | 물리 지식 설명 | Self-RAG ← **현재 구현** | 메인 챗 |
| 논문 분석기 (②) | abstract 트리아지 → 전문 요약·평가 → VDB 저장 | 파이프라인 서브그래프 | 추천(③)·수동 ingest(④)·논문 자체 검토(⑦) — **허브 능력** |
| 문서 작성기 (①⑤ 공용) | 대화 → 템플릿 문서 변환, 유사도 중복 검사(신규 대신 기존 편집 제안), 등록 확인 `interrupt` | HITL | 모든 표면 — 템플릿만 갈아끼움(관심사/실험도구) |
| 가설 수립 | 검증 가능한 가설 생성 | - | 연구 워크플로우 |
| 실험 설계 | 가설 → 실험 프로토콜 (변수·통제조건·장비) | Plan-and-Execute | 연구 워크플로우 |
| 실험 운영 | 도구·자원 점검, 진행 추적, 결과 분석 → 재설계 요청 | - | 연구 워크플로우 |
| 논문 작성 | 실험 결과·사용자 문서 기반 초안 → ②로 자체 검토·재작성. 워크플로우가 누적한 references 목록 소비 + 인용-근거 일치 검증 | Evaluator-Optimizer | 연구 워크플로우 |
| 참고문헌 추천기 | 텍스트(초안 문단·답변)에서 주장·키워드 추출 → 요약 VDB 검색 → 부족 시 arxiv 검색 → ② 트리아지 → 관련도 랭킹·서지 리스트 | 온디맨드 (③과 검색·평가 내부 공용) | 연구 워크플로우 각 단계 · 논문 작성(⑦) · 메인 챗(④) 온디맨드 |
| 추천 검색 (③) | 관심사 기준 논문 검색 → ② 트리아지·평가 → 랭킹 → 카탈로그에 recommended로 기록. 권위 논문 목록(인용수 기반)도 조회·캐시 | **관심사에서 트리거할 때만** 실행 (cron 아님) | 라이브러리 관심사 탭 · 메인 챗 |
| 피드 수집 | hype 소식 크롤링 → 키워드 태깅 → 관심사 키워드 매칭(강조·정렬용) | cron 배치 | 피드 표면 |
| 번역 레이어 | 응답 직전 한국어 후처리 (원문 병기) | 후처리 노드 | 표면 공용 |

### 데이터 서비스 — CRUD + 검색 (저장에 LLM 불필요)

| 저장소 | 내용 | 형태 |
|---|---|---|
| 관심사 저장소 (①) | 사용자 관심사 문서 (템플릿 기반) | VDB 컬렉션 — 유사도 검색으로 중복 검사 |
| 논문 요약 VDB (②) | 논문 분석기가 쌓는 요약·평가 | VDB 컬렉션 — 메타데이터(arxiv id·평가·관심사 태그 + **서지정보: 제목·저자·연도** — 인용 포맷(BibTeX 등)의 전제) |
| 논문 카탈로그 | 논문 상태·서지 관리 (요약 VDB는 내용 검색용, 카탈로그는 상태 관리용 — 역할 분리) | 구조화 레코드(SQLite), **DOI가 기본 키**. `status: recommended / owned / dismissed` — 등록 시 DOI 매칭으로 recommended → owned 자동 전환(추천 목록에서 내려감) |
| 지식 노트 | 사용자의 지식체계 (노트·정리 문서) | VDB 컬렉션 — `source_type: user_note`로 논문·코퍼스와 **신뢰도 구분** (RAG 검색은 되지만 사실 근거로는 논문·코퍼스 우선) |
| 실험도구 DB (⑤) | 장비 spec 문서 | 구조화 레코드(정확 조회 필요) + 선택적 임베딩 |
| 코퍼스 | 파인만 강의록 | ChromaDB (현재 구현) |
| 안전 규칙 | 실험 안전 가드레일 | 규칙 기반 — 설계·운영 양 단계 공통 조회 |

### 설계 포인트

- **논문 분석기(②)가 허브**: ③(추천 필터)·④(수동 ingest)·⑦(자체 검토)이 전부 재사용하는 부품이라 멀티 에이전트 확장 시 가장 먼저 만든다. 사용자와 직접 대화하지 않으므로 챗봇이 아니다.
- **피드와 추천의 분리**: 피드는 관심사와 무관한 hype 소식을 cron으로 싸고 넓게 수집(키워드 태깅 → 관심사 일치 키워드만 색 강조 + 상단 정렬), 추천 검색(③)은 관심사에서 트리거할 때만 비싸고 깊게 실행(② 평가 포함). 추천 리스트에서 끝나고 구매·ingest는 사람이 밖에서 결정 — 그래프 차원의 HITL이 아니다 (기존 결정 유지). 등록되면 카탈로그 DOI 매칭으로 추천 목록에서 자동으로 내려간다.
- **외부 API는 최종 단계의 어댑터**: 유료 저널 대응(Crossref 신착 감지, Unpaywall/CORE OA 본문, OpenAlex 인용수·권위 논문)은 검색 함수 뒤에 숨는 구현 세부 — 초기엔 arxiv·웹 검색만으로 전 기능을 완성하고, API 어댑터는 마지막에 갈아끼운다. API 연결 자체가 목표가 되지 않게.
- **프론트 스택 재검토 예정**: 표면이 4개(챗·워크플로우·라이브러리·피드)가 되면 Streamlit만으로는 한계 — 지금은 Streamlit(multipage)로 버티고, 라이브러리·피드 구축 시점에 React 등 전환을 검토.
- **"관심사로 등록할까요?" 제안은 턴 종료 후 훅**: 에이전트가 아니라 챗 그래프의 final_answer 뒤에서 싼 모델로 1회 판정 → 제안 → 수락 시 문서 작성기 호출. 한 번 구현해 모든 표면에 붙인다.
- **가설 수립과 실험 설계 분리**: 가설을 세우는 일(귀추적 추론)과 검증 가능한 실험으로 번역하는 일(방법론·장비·통제조건)은 성격이 다른 작업. 재실험·대체실험 루프는 실험 운영이 **실험 설계만 재호출** — 가설은 고정한 채 프로토콜만 다시 짜는 게 흔한 경로라 매번 가설부터 재추론하면 낭비 (기존 결정 유지).
- **참고문헌은 워크플로우가 끌고 다니는 누적 산출물**: 가설 수립(배경 문헌) → 실험 설계(방법론) → 실험 운영(결과 비교) → 논문 작성(고찰) 각 단계가 참고문헌 추천기를 호출해 공유 references 목록에 append(서지정보 + 인용 이유 + 추가된 단계 기록), ⑦이 최종 소비자. 목록에 없는 인용이 초안에 등장하면 그 자체가 환각 신호 — 자체 검토에서 걸러낸다. QA(④)에서는 기본은 retrieve가 이미 가져온 문서의 메타데이터를 "참고"로 붙이고(추가 호출 0), 사용자가 요청할 때만 추천기 풀 호출(라우터 분기).
- **안전 가드레일 (Human-in-the-loop)**: 실험 안전은 각 능력이 자체 판단하지 않고 공유 규칙을 설계·운영 양 단계에서 공통 조회. 임계치 초과 시 사람 승인 전까지 진행 불가 — `interrupt_before` 기반 진짜 HITL이 필요한 지점은 여기(와 문서 작성기의 등록 확인)뿐이다. interrupt로 멈춘 상태가 서버 재시작에 살아남아야 하므로 **SqliteSaver 영속화가 선행**된다.
- **긴 작업·진행상황은 스트리밍 전제**: 연구 워크플로우와 실시간 진행상황 안내는 동기 요청-응답으로는 불가능 — `astream` + SSE 엔드포인트를 워크플로우 구축 전에 도입한다.
- **멀티 에이전트 전환은 재작성이 아니라 포장**: 현 그래프를 물리 QA 능력으로 감싼다. 단 컴파일된 그래프를 부모 노드로 직접 꽂지 않고 **래퍼 함수 노드에서 `invoke()`로 입출력을 명시 매핑** — 부모와 State 스키마(특히 `messages` reducer)를 공유하지 않아 내부 상태가 밖으로 새지 않는다. checkpointer와 턴 경계(reset_turn)는 부모 소속으로 이동.

## 현재 구현 — Self-RAG 에이전트

```
START → retrieve → generate ──(tool 요청)──→ run_tools ──→ generate (ReAct 루프)
             ↑          └─(답변 완성)→ verify ──── 통과 ────→ final_answer → END
             │                          ├── 수정 필요 → generate (재시도)
             └──────────────────────────┘── 컨텍스트 부족 → retrieve (top_k+1)
```

> **[아키텍처 개편]** 이 그래프(`graph.py`)는 이제 "물리 QA" 능력(서브그래프)이다 — 자체 checkpointer가 없고, `orchestrator.py`가 매번 fresh하게 `.invoke()`로 호출한다. 예전엔 `reset_turn` 노드가 매 턴 진입 시 임시 상태를 초기화했는데, fresh invoke 자체가 Pydantic 기본값으로 이미 초기화된 상태라 이 노드가 통째로 불필요해졌다 — 단기기억(대화 이력)·턴 경계·체크포인터는 이제 `orchestrator.py`가 소유한다.

- **retrieve**: 벡터 검색 (기본 top_k=3). 재검색 시 벡터DB 문서는 교체하되 tool로 수집한 증거는 보존
- **generate**: 대화 이력(`add_messages` reducer) 기반 답변 생성. tool이 필요하면 `tool_calls`만 요청 — 실행은 run_tools 노드 담당. 재시도 시 verify의 지적사항을 대화 메시지로 반영
- **run_tools**: tool 실행 + 예외처리. 모든 tool_call에 반드시 ToolMessage로 응답(실패 포함) → LLM이 다음 라운드에 에러를 읽고 자가수정. 빈 결과·호출 실패·미등록 tool을 구분해 다른 힌트 제공, **연속 2회 실패한 tool은 해당 런에서 자동 제외(서킷 브레이커)**. 성공 결과는 Document로 변환해 RAG context에 병합
- **verify**: 구조화 출력(`fix_needed`, `what_to_fix`, `needs_more_context`)으로 답변 검증. **생성 모델과 다른 모델이 검증** (교차 검증) — generate가 fallback으로 갈아탄 경우에도 실제 생성 모델(`generated_by`)을 기준으로 회피하며, 가용 모델이 하나도 안 남으면 차순위로 생성자 본인이 검증
- **route_by_fix**: 3방향 분기. `try_count >= limit` 시 강제 종료 + 실패 사유 명시
- **final_answer — 출력 이원화**: `answer`(답변 본문, 평가 대상)와 `comment`(부가 정보, 사용자 전용)를 분리. 재시도를 거친 답변만 structured output으로 본문/메타를 분리하고(평시 추가 호출 0), limit 도달·fallback 발생 같은 시스템 고지는 코드가 comment에 작성 — 실패해도 사용자에게 정직하게 알린다
- **State**: Pydantic 모델 — 필드 기본값·타입 검증, `messages`는 `add_messages` reducer로 자동 누적

### 특징

- **단기기억 (멀티턴 대화)**: `MemorySaver` checkpointer + `thread_id` — **이제 `orchestrator.py`가 소유**(물리 QA 능력 자체는 checkpointer 없이 fresh invoke). 같은 thread_id로 요청하면 대화 이력이 이어져 후속 질문("방금 답을 요약해줘")이 가능. thread_id 미지정 시 uuid가 자동 발급되어 단발 요청도 안전. verify에는 "맥락상 답할 수 없는 모호한 질문에 명확화를 요청한 답변은 정확한 대응" 기준을 추가해 멀티턴 특유의 불완전한 질문에 대응. (MemorySaver는 프로세스 메모리라 서버 재시작 시 소멸 — 영속화는 SqliteSaver로 예정)
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
├── orchestrator.py       # 부모 그래프 — 단기기억·checkpointer 소유, 능력(물리 QA 등) 호출·라우팅
├── graph.py              # 물리 QA 능력 (Self-RAG 서브그래프) — checkpointer 없음, orchestrator가 fresh invoke
├── models.py             # model_map + invoke_with_fallback (모델 등록·fallback 정책의 단일 지점)
├── tool.py               # tool 레지스트리 (검색 tool 팩토리, tools_list, tool_map)
├── arxiv_api.py          # arxiv 공식 API 직접 호출 (구조화된 서지정보 — 논문 분석기·arxiv 검색 tool이 공유)
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
- `_add_tokens` — 토큰 누적 헬퍼 (provider가 얹어주는 낯선 키를 무시하는지)
- `invoke_with_fallback` — `model_map`을 통째로 모킹해서, 진짜 API 호출 없이 fallback·서킷 브레이커 로직만 검증

`tests/conftest.py`가 두 가지 import-time 문제를 미리 막아준다: `retrieval.py`의 무거운 임베딩 모델 로딩(가짜 모듈로 대체), `models.py`의 `model_map` 생성 시 API 키 존재 검사(더미 키로 통과, 로컬 `.env` 값은 덮어쓰지 않음). 그래서 CI에도 별도 API 키 Secret 없이 그대로 돈다.

`.github/workflows/deploy.yml`의 `test` job이 이 테스트를 빌드·배포 전에 자동 실행하는 게이트 역할을 한다 — 실패하면 `deploy` job(이미지 빌드+push+EC2 배포)은 시작조차 안 됨. 상세: [docs/README_11.md](docs/README_11.md#8-테스트-게이트).

## API

```
POST /query
{
  "prompt": "파인만이 설명한 원자가 뭐야?",
  "model": "gemini",
  "thread_id": "user-123"
}

→ {"answer": "...", "comment": "..."}
```

- `model`: `"gemini"` (기본값) / `"claude"` / `"Qwen-tuned"` (로컬 llama-server 필요)
- `thread_id`: 대화 세션 식별자 — 같은 값으로 요청하면 이전 대화 맥락이 이어짐(단기기억). 생략 시 uuid 자동 발급(맥락 없는 단발 요청)
- `top_k`/`limit`(검색 문서 수·verify 재시도 한도)은 물리 QA 능력 내부 다이얼이라 API에서 빠짐 — 지금은 `orchestrator.py`가 기본값(top_k=3, limit=4)으로 호출. 능력이 여러 개로 늘어나면(6-7 라우터) 능력별 파라미터 노출 방식을 다시 설계할 예정
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
