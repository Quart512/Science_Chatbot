# AIsaac — 물리 연구 어시스턴트

물리 연구를 돕는 개인용 AI 어시스턴트. 내려받아 자기 컴퓨터에서 실행한다.

- **묻고 답하기** — 과학·수학 질문에 등록해둔 자료와 웹 검색을 근거로 답한다
- **논문 관리** — PDF나 DOI·arXiv 번호로 논문을 등록하면 자동으로 요약해주고, 관심사를 등록해두면 관련 논문을 찾아 추천한다
- **연구 진행** — 가설 수립 → 실험 설계 → 실험 운영 → 보고서 → 논문 초안까지 단계별로 함께 진행한다

## 문서 안내

역할별로 문서를 나눠 뒀다. 무엇을 고칠 때 어디를 보면 되는지:

| 문서 | 담는 내용 | 업데이트 시점 |
|---|---|---|
| **README.md** (이 문서) | 현황 — 무엇을 하는 앱인가, 구조, 실행법, API. **"왜 이렇게 됐는지"는 안 적는다** | 사실이 바뀔 때만 (API·명령어·구조 변경) |
| **[docs/DEPLOY.md](docs/DEPLOY.md)** | 배포 방법 (설치·운영 절차) | 배포 절차·환경이 바뀔 때 |
| **[docs/RoadMap.md](docs/RoadMap.md)** | 개발 이력(완료)·**🧪 라이브 검증 체크리스트**·예정 + 설계 노트·열린 질문·방향성 메모 (날짜별 이력의 단일 진실 소스) | 상시 — 진행 상황이 바뀔 때마다. **pytest로 못 잡아 미뤄둔 확인이 생기면 체크리스트에 추가** |
| **To Do List** (Obsidian 칸반) | 실행 순서만 (한 줄 요약 — **세부 내용의 정본은 RoadMap**) | 상시 — RoadMap과 짝으로 동기화 |
| **docs/README_08~13.md** | 주차별 개발 회고 (아카이브) — "무엇을 했는지"가 아니라 "왜 그렇게 했는지"와 겪은 문제 위주 | 해당 구간 마무리 시 1회 |

> 평소엔 **RoadMap ↔ To Do List**만 동기화하면 된다. 완료한 기능이 현황을 바꾸는 순간(예: 프론트엔드 추가 → 실행법 변경)에만 README/DEPLOY도 함께 손본다.

## 구조

**화면(표면) / 기능(능력) / 저장소** 3층으로 나뉜다.

![화면/기능/저장 3층 구조](docs/architecture.png)

> 그림은 `uv run docs/draw_architecture.py`로 다시 만든다 (`docs/draw_architecture.py`의 박스 정의만 고치면 된다).

핵심 원칙: **챗봇을 여러 개로 쪼개지 않고, 작업 성격에 맞는 화면을 준다** — 대화는 챗, 등록·조회는 폼, 연구는 단계형 워크플로우. 상시 대화하는 챗봇은 메인 챗 하나뿐이고 나머지는 버튼·폼을 눌렀을 때 호출되는 기능으로 존재한다.

### 화면 — 사용자가 만나는 곳

| 화면 | 형태 | 내용 |
|---|---|---|
| 메인 챗 | 상시 대화형 | 과학·수학 등 궁금한 것을 물어보면 라이브러리에 등록해둔 자료와 웹을 검색해 답해준다 |
| 연구 워크플로우 | 단계형 (다음 단계로의 전환은 사용자가 직접 누름) | 연구 주제 하나를 정하면 가설 수립 → 실험 설계 → 실험 운영 → 실험 보고서 → 논문 초안까지 단계별로 이어서 진행하는 화면. 진행 상황이 그대로 남아 있어 이전 단계로 돌아가 다시 볼 수도 있다 |
| 라이브러리 | 관리 UI (탭) | 관심사·논문·실험도구·지식 노트를 등록·조회·관리하는 화면. 관심사를 등록하면 관련 논문을 찾아 추천해주고, 논문은 PDF나 DOI·arXiv 번호로 등록하면 자동으로 요약해준다 |

> 피드(관심 분야 최신 소식을 모아 보여주는 화면)는 아직 없다.

### 기능 — 화면 뒤에서 실제 일을 하는 것들

메인 챗 안에서, 또는 라이브러리·연구 워크플로우 화면의 버튼·폼을 눌렀을 때 호출돼 일을 하고 끝나는 기능들이다.

| 기능 | 무엇을 해주는가 | 어디서 만나는가 |
|---|---|---|
| 물리 QA | 물리 질문에 답한다. 답변에 어떤 자료를 근거로 삼았는지 같이 보여주고, 스스로 답을 점검해 부족하면 더 찾아보고 고쳐 쓴다 | 메인 챗 |
| 논문 요약기 | 라이브러리에 등록한 논문을 자동으로 읽고 핵심 주장·근거·저자가 스스로 밝힌 한계와 아직 안 풀린 문제를 정리해 보여준다. 논문을 평가하지는 않는다 — 저자가 쓴 내용을 그대로 뽑아 보여줄 뿐이다 | 라이브러리 논문 탭, 메인 챗(관련 논문이 있으면 참고 자료로 함께 인용) |
| 논문 스크리닝 | 검색된 논문 중 등록해둔 관심사와 실제로 관련 있는 것만 골라준다. 심사받은 학술지인지·인용 수·발표 연도도 같이 보여주되 하나의 점수로 합치진 않는다 — 최종 판단은 사용자 몫이다 | 추천 검색·참고문헌 추천기 뒤에서 자동으로 함께 동작 |
| 논문 검색 | 관심 주제와 관련된 논문을 인터넷(arXiv 등)에서 찾아온다 | 추천 검색·참고문헌 추천기 뒤에서 자동으로 함께 동작 |
| 문서 작성기 | 챗에서 나눈 대화를 바탕으로 관심사·실험도구 등록 폼을 미리 채워준다. 확인하고 저장 버튼만 누르면 된다 | 라이브러리의 "이 대화를 관심사로 등록" 같은 버튼 |
| 가설 수립 | 연구하고 싶은 주제를 알려주면 검증할 수 있는 형태의 가설과 그 근거를 세워준다 | 연구 워크플로우 |
| 실험 설계 | 세운 가설을 실제로 확인할 수 있는 실험 절차(무엇을 바꾸고 무엇을 측정할지, 어떤 장비가 필요한지)를 짜준다 | 연구 워크플로우 |
| 실험 운영 | 실제로 진행한 실험 결과를 입력하면 가설이 맞았는지, 실험 자체에 문제가 있었는지, 다시 해봐야 하는지를 판단해준다. 실험은 사람이 직접 하고 이 기능은 결과 해석만 한다 | 연구 워크플로우 |
| 논문 작성 | 가설 수립부터 실험 운영까지의 과정과 모아둔 참고문헌을 종합해 논문 초안(제목·초록·서론·방법·결과·고찰)을 써준다 | 연구 워크플로우 |
| 참고문헌 추천기 | 지금 보고 있는 글(논문 초안 문단, QA 답변 등)과 관련된 논문을 찾아 인용할 만한 후보로 추천해준다 | 연구 워크플로우 각 단계에서 자동으로 함께 동작 |
| 추천 검색 | 등록해둔 관심사를 기준으로 논문을 찾아 추천 목록에 올려준다. 자동으로 도는 게 아니라 "검색" 버튼을 눌렀을 때만 동작한다 | 라이브러리 관심사 탭 |
| 피드 수집 (아직 없음) | 관심 주제와 무관하게 요즘 화제가 되는 논문·소식을 모아 보여준다 | — |
| 번역 레이어 (아직 없음) | 답변을 자연스러운 한국어로 한 번 더 다듬어준다 | — |

### 데이터 저장 — 무엇이 어디에 남는가

| 저장소 | 내용 |
|---|---|
| 관심사 저장소 | 등록한 관심사(찾는 것·이미 아는 것·제외할 주제) |
| 논문 저장소 | 등록한 논문의 원문·요약·서지정보(제목·저자·연도)·상태(추천/보유/기각) |
| 지식 노트 | 사용자가 쓴 노트 |
| 실험도구 목록 | 등록한 실험 장비 사양과 주의사항 |
| 코퍼스 | The Feynman Lectures on Physics |

> 설계 판단(왜 이렇게 나눴는지, VDB/RDB 선택 근거 등)은 이 문서가 아니라 [docs/RoadMap.md](docs/RoadMap.md)의 설계 노트에 정리돼 있다.

## 기술적으로 어떻게 동작하는가 (개발자용)

물리 QA는 한 번에 답하고 끝나지 않는다 — 관련 자료를 검색하고, 답을 쓰고, 스스로 검증해서 부족하면 다시 검색하거나 고쳐 쓰는 과정을 거친다. 논문 등록도 등록(파싱해서 검색 가능하게 만들기)과 요약 생성을 분리해뒀다 — 요약은 실제로 필요할 때(라이브러리에서 펼쳐볼 때, QA가 참고할 때) 그 자리에서 만들고 캐시해둔다.

내부 구조와 각 설계 판단의 근거는 이 문서가 아니라 [docs/RoadMap.md](docs/RoadMap.md)(설계 노트)와 주차별 회고(`docs/README_08.md` ~ `README_13.md`)에 정리돼 있다.

## 파일 구조

```
Science_Chatbot/
├── docs/
│   ├── architecture.png     # 구조도 (draw_architecture.py로 생성)
│   ├── draw_architecture.py # 구조도 생성 스크립트
│   ├── feynman.txt          # 코퍼스: The Feynman Lectures on Physics
│   ├── RoadMap.md           # 개발 이력·계획 (완료/예정 + 설계 노트)
│   ├── DEPLOY.md            # 배포 가이드 (빅뱅/Docker 방식)
│   ├── README_08.md         # 개발 회고 (8주차: LangGraph 에이전트)
│   ├── README_09.md         # 개발 회고 (9주차: QLoRA 파인튜닝·양자화·GGUF)
│   ├── README_10.md         # 개발 회고 (10주차: 서버 관찰·패킷 캡처)
│   ├── README_11.md         # 개발 회고 (11주차: Docker·EC2·CI/CD)
│   ├── README_12.md         # 개발 회고 (CI/프론트엔드 정비·아키텍처 개편·논문 요약기 완성)
│   ├── README_13.md         # 개발 회고 (라이브러리 표면 1차·관심사 재검색·실험도구 DB(⑤)·연구 워크플로우(⑥))
│   └── train_qa.json        # 파인튜닝 학습 데이터 45문항 (파인만 강의록 기반)
├── tests/
│   ├── conftest.py                  # 공용 설정 — retrieval import-time 로딩 차단, API 키 더미값, make_state fixture
│   ├── test_routing.py              # route_by_fix (순수 라우팅 함수)
│   ├── test_tokens.py               # add_tokens (models.py의 토큰 누적 헬퍼 — 물리 QA·연구 워크플로우 공용)
│   ├── test_invoke_with_fallback.py # invoke_with_fallback (모델 fallback, model_map 모킹)
│   ├── test_arxiv_api.py            # arxiv Atom XML 파싱(journal_ref/doi 포함) + fetch_by_id (네트워크 없이)
│   ├── test_context_budget.py       # check_context_budget / ContextBudgetExceeded
│   ├── test_paper_id.py             # paper_id 정규화 (DOI/arXiv/해시 우선순위)
│   ├── test_paper_chunking.py       # 헤더 분할·References/Abstract 태깅·임베딩용 청킹
│   ├── test_paper_ingest.py         # register_paper/get_paper_summary/track_in_background (가짜 vectorstore 주입)
│   ├── test_describe_context_sources.py  # QA 답변 근거 표시(graph.py, 메타데이터만으로 포매팅)
│   ├── test_retrieve.py             # retrieve()의 feynman+papers 컬렉션 병합
│   ├── test_interests.py            # 관심사 RDB CRUD (실제 sqlite3 :memory: 연결, 가짜 불필요)
│   ├── test_paper_catalog.py        # 논문 카탈로그 RDB CRUD (상태 전이: recommended/owned/dismissed)
│   ├── test_paper_search.py         # 논문 검색 어댑터 (arxiv_search 몽키패치, paper_id 조립)
│   ├── test_paper_screening.py      # 논문 스크리닝(②b) — 관련도만 LLM 몽키패치, peer_reviewed/인용수/연도는 계산 검증
│   ├── test_paper_recommend.py      # 추천 검색(③) 오케스트레이션 — 검색→스크리닝→카탈로그 기록 조립 로직
│   ├── test_equipment.py            # 실험도구 RDB CRUD + 스키마 마이그레이션(구버전 테이블에 컬럼 추가)
│   ├── test_knowledge_notes.py      # 지식 노트 CRUD — 본문은 SQLite(:memory:), VDB는 FakeVectorstore로 재색인 시점만 확인
│   ├── test_reference_recommender.py # 참고문헌 추천기 — 보유 VDB 우선/외부 보충 분기, 서킷 브레이커 전파
│   ├── test_research_workflow.py    # 연구 워크플로우(⑥⑦) 노드 + stage 라우팅(MemorySaver로 5단계 통과)
│   ├── test_research_sessions.py    # 연구 세션 목록 RDB CRUD (실제 sqlite3 :memory: 연결, PK가 thread_id)
│   ├── test_orchestrator.py         # 대화 이력 트리밍(_trim_history), 관심사 초안 추출(draft_interest_from_messages)
│   └── test_main.py                 # POST /interests, /interests/{id}/search, /equipment, /research/{id}/advance (TestClient, 몽키패치)
├── evaluation/
│   ├── eval.json             # 평가 데이터셋 31문항 (질문/정답/카테고리/난이도/unsolved)
│   ├── eval.md               # eval.json에서 자동 생성되는 카테고리별 표
│   ├── generate_eval_md.py   # eval.json → eval.md 생성 스크립트
│   ├── evaluate.py           # LLM-as-judge 평가 (--target으로 평가 대상 선택)
│   ├── eval_avg.py           # results/의 실행별 평균 점수 요약
│   └── results/               # evaluate.py 실행 결과 (모델별 JSON)
├── models/               # GGUF 모델 가중치 (git 제외)
├── chroma_db/            # ChromaDB 영구 저장소
├── data/                 # SQLite 파일들 (git 제외) — checkpoints.sqlite(대화 이력) + research_workflow_checkpoints.sqlite(연구 워크플로우) + app.db(관심사·논문 카탈로그·실험도구), 파일은 분리하되 디렉터리는 공유
├── orchestrator.py       # 부모 그래프 — 단기기억·checkpointer 소유, 능력(물리 QA 등) 호출·라우팅
├── graph.py              # 물리 QA 능력 (Self-RAG 서브그래프) — checkpointer 없음, orchestrator가 fresh invoke
├── models.py             # model_map + invoke_with_fallback + CONTEXT_BUDGET_CHARS/check_context_budget + add_tokens(토큰 누적 공용 헬퍼)
├── tool.py               # tool 레지스트리 (검색 tool 팩토리, tools_list, tool_map)
├── arxiv_api.py          # arxiv 공식 API 직접 호출 (구조화된 서지정보 — 논문 요약기·arxiv 검색 tool이 공유)
├── paper/                # 논문 파이프라인(파싱→분할→식별→추출→저장)
│   ├── pdf_parse.py          # PDF 파싱 어댑터 (PyMuPDF/pymupdf4llm 격리, AGPL 고지)
│   ├── paper_chunking.py     # 헤더 기반 섹션 분할(추출용)·임베딩용 청킹·References 태깅
│   ├── paper_id.py           # 논문 불변 식별자 정규화 (DOI > arXiv > 파일 해시)
│   ├── paper_extraction.py   # 논문 구조화 추출 Pydantic 스키마 (품질 판정 아님)
│   └── paper_ingest.py       # 논문 요약기(②a) 오케스트레이션 — register_paper/get_paper_summary/track_in_background
├── retrieval.py          # 임베딩 + 벡터스토어(feynman, papers) — ingest/paper_ingest와 공유해 임베딩 모델 불일치 방지
├── ingest.py             # 인덱싱: 청킹 → 로컬 임베딩 → ChromaDB
├── interests.py          # 관심사 저장소(①) RDB(SQLite) — data/app.db, ORM 없이 표준 라이브러리 sqlite3
├── paper_catalog.py      # 논문 카탈로그 RDB(SQLite) — data/app.db(interests.py와 같은 파일, 다른 테이블), status: recommended/owned/dismissed
├── paper_search.py       # 논문 검색 어댑터 — arxiv_search()를 감싸 paper_id·지표 자리까지 채운 후보 목록 반환(나중에 Crossref/OpenAlex로 교체 대비)
├── paper_screening.py    # 논문 스크리닝(②b) — 관련도만 LLM 판단, peer-review/인용수/연도는 계산·전달(한 점수로 안 합침)
├── paper_recommend.py    # 추천 검색(③) — 검색→스크리닝→카탈로그 recommended 기록 오케스트레이션, 관심사 수정 시 재검색(refresh_for_interest)
├── equipment.py          # 실험도구 저장소(⑤) RDB(SQLite) — data/app.db 공유(다른 테이블). precautions는 ⑥ 안전 가드레일이 읽음
├── knowledge_notes.py    # 지식 노트 — 본문은 RDB(SQLite, data/app.db 공유), VDB(notes_vectorstore)는 검색용 청크만 담는 disposable 인덱스(수정 시 통째로 재색인)
├── reference_recommender.py  # 참고문헌 추천기 — 텍스트→검색어 추출→보유 논문 VDB 우선→부족하면 검색+②b 스크리닝 (⑥ 각 단계·⑦·④ 공용 함수)
├── research_workflow.py  # 연구 워크플로우(⑥⑦) 그래프 — 가설 수립→실험 설계→실험 운영→실험 보고서→논문 초안. stage로 START 라우팅(단계 전환은 사람 트리거), 체크포인트 파일 별도
├── research_sessions.py  # 연구 세션 목록(⑥) RDB(SQLite) — data/app.db 공유, PK는 thread_id(호출자가 uuid4() 발급)
├── main.py               # FastAPI: /query, /interests(+CRUD), /interests/{id}/search·/refresh, /papers, /equipment(+CRUD), /research/sessions(+CRUD)·/research/{id}/advance·/research/{id}(+/history)·/research/{id}/draft
├── frontend-react/       # React+TypeScript SPA(Vite) — 왼쪽 네비게이션 + 가운데 라우팅 콘텐츠 + 오른쪽 항상 떠 있는 챗 패널 3분할 셸. 메인 챗·연구 워크플로우·라이브러리(논문/관심사/실험도구/지식노트) 전 화면 구현
└── .env                  # API 키 (git 제외)
```

## 사전 준비

| 도구 | 용도 | 설치 |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | 파이썬 버전·패키지 관리 (필수) | `brew install uv` 또는 `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 자체 모델(GGUF) 로컬 서빙 — `Qwen-tuned` 사용 시에만 | `brew install llama.cpp` |

Python은 따로 설치하지 않아도 된다 — `uv sync`가 `pyproject.toml`의 `requires-python`에 맞는 버전을 자동으로 받아온다. 파이썬 패키지 의존성 전체는 `pyproject.toml`에 선언되어 있고 `uv sync` 한 번으로 설치된다. API 키는 아래 [환경변수](#환경변수-env) 참고.

## 실행

> 아래는 로컬 개발용 최소 실행법이다. 배포판(Docker Compose 등)으로 띄우는 방법은 **[docs/DEPLOY.md](docs/DEPLOY.md)** 참고.

```bash
# 의존성 설치
uv sync

# 인덱싱 (최초 1회)
uv run ingest.py

# 서버
uv run fastapi dev main.py

# 단독 실행 (터미널 테스트)
uv run graph.py

# (선택) 논문 한 편 등록 + 요약 생성 — 화면 없이 터미널에서 바로
uv run -m paper.paper_ingest <PDF 경로> [arxiv_id]

# (선택) 자체 파인튜닝 모델 서빙 — model: "Qwen-tuned" 사용 시 필요
llama-server -m models/qwen_finetuned_Q4_K_M.gguf --port 8080
```

> **GGUF 참고**: 모델 가중치(941MB)는 용량 문제로 저장소에 포함되지 않는다 (`models/`는 git 제외). `Qwen-tuned` 없이도 gemini/claude로 모든 기능이 동작하며, 파인튜닝 과정은 [docs/README_09.md](docs/README_09.md)에 기록되어 있다.

> **임베딩 모델 참고**: `BAAI/bge-m3`는 별도 설치가 필요 없다 — 첫 실행 시 Hugging Face Hub에서 자동 다운로드된다 (약 2GB, `~/.cache/huggingface`에 캐시). 이후 실행은 캐시를 사용하므로 빠르며, API 키·네트워크 없이 로컬에서 동작한다. 단 `ingest.py`와 `graph.py`는 반드시 같은 임베딩 모델을 써야 한다 (모델이 다르면 벡터 공간이 달라져 유사도 검색이 무의미해짐).

## 테스트

```bash
uv run pytest
```

실제 LLM 호출·벡터DB·임베딩 모델 없이(모두 모킹 또는 회피) 몇 초 안에 끝나는 유닛 테스트. "노드 내부 구현"이 아니라 "여러 노드가 공유하는 지점"·순수 함수·명시적 설계 결정만 골라서 검증한다 — 어떤 구현이 어떻게 바뀌든, 그 지점을 통과하는 입출력이 규격만 지키면 테스트는 그대로 유효하다는 원칙. 대표적으로:

- `route_by_fix` — 순수 라우팅 함수 (State만 보고 다음 노드 결정)
- `invoke_with_fallback` — `model_map`을 통째로 모킹해서, 진짜 API 호출 없이 fallback·서킷 브레이커 로직만 검증
- `paper_id.normalize_paper_id` — DOI > arXiv > 파일 해시 우선순위, 재등록 멱등성
- `paper_chunking.split_into_chunks`/`split_for_embedding` — 헤더 분할·병합, References 태깅
- `paper_ingest.register_paper`/`get_paper_summary` — 가짜 vectorstore·가짜 LLM 응답을 주입해 등록·lazy 요약·캐시 로직만 검증
- `graph.retrieve` — feynman·papers 두 컬렉션 검색 결과 병합 (가짜 vectorstore 주입)

`tests/conftest.py`가 두 가지 import-time 문제를 미리 막아준다: `retrieval.py`의 무거운 임베딩 모델 로딩(가짜 모듈로 대체), `models.py`의 `model_map` 생성 시 API 키 존재 검사(더미 키로 통과, 로컬 `.env` 값은 덮어쓰지 않음). 그래서 CI에도 별도 API 키 Secret 없이 그대로 돈다.

CI는 `.github/workflows/test.yml`(재사용 워크플로우)에 pytest 실행 스텝을 하나만 두고 두 군데서 쓴다: PR(main 대상)에 직접 붙어 merge 전에 결과가 보이고, `deploy.yml`의 `test` job이 이걸 `uses:`로 재사용해 push(main) 시 게이트로도 쓴다 — 실패하면 `publish` job(이미지 빌드+Docker Hub push)은 시작조차 안 된다.

## API

```
POST /query
{
  "prompt": "파인만이 설명한 원자가 뭐야?",
  "model": "gemini",
  "effort": "medium",
  "thread_id": "user-123"
}

→ text/event-stream (SSE) — 진행 중엔 {"trace": "...", "final": false},
  답변 도착 시 {"trace": "...", "answer": "...", "comment": "...", "final": true}
```

- `model`: `"gemini"` (기본값) / `"claude"` / `"Qwen-tuned"` (로컬 llama-server 필요)
- `effort`: `"low"`/`"medium"`(기본값)/`"high"` — 검색 문서 수·재시도 횟수를 한 번에 정하는 프로필(숫자 매핑은 `graph.py`의 `EFFORT_PROFILES`)
- `thread_id`: 대화 세션 식별자 — 같은 값으로 요청하면 이전 대화 맥락이 이어진다(`data/checkpoints.sqlite`에 저장돼 서버를 껐다 켜도 남는다). 생략 시 uuid 자동 발급(맥락 없는 단발 요청)
- 응답의 `answer`는 답변 본문, `comment`는 부가 정보 — 모델의 주의점, 재시도 한도 도달·모델 전환 고지 등. 정상 처리 시 comment는 비어 있을 수 있음

```
POST /interests
{
  "title": "위상 물질",
  "looking_for": "기초 개념",
  "already_known": "",
  "excluded_topics": "",
  "update_existing_id": null
}

→ {"interest_id": 1, "action": "created"}   (update_existing_id 지정 시 "updated", 없는 id면 404)
```

- 관심사 저장소(`interests.py`, `data/app.db`)에 저장. 화면의 폼 값을 그대로 보내는 단발 요청이다

```
GET /interests/draft?thread_id=user-123
→ {"draft": {"title", "looking_for", "already_known", "excluded_topics"}}
```

- 챗 사이드바의 "이 대화를 관심사로 등록" 버튼이 부른다 — 그 대화 이력을 읽어 초안만 뽑고 저장은 안 한다(저장은 사용자가 폼에서 확인한 뒤 `POST /interests`)

```
POST /interests/{interest_id}/search

→ {"recommended": [{"paper_id", "is_relevant", "reasoning", "peer_reviewed",
                     "citation_count", "year", "title", "abstract"}, ...]}
```

- 그 관심사 기준으로 논문을 검색(arxiv)하고 관련도를 판정한다. 사용자가 버튼을 눌렀을 때만 실행된다. 카탈로그에는 관련 있다고 판정된 것만 `recommended`로 기록되지만, **응답 목록엔 관련 없다고 판정된 것도 포함**된다(판정이 틀릴 수 있어 사용자가 직접 보고 판단할 여지를 남긴다). 정렬은 관련도 기준 하나뿐 — `peer_reviewed`/`citation_count`/`year`는 표시만 하고 정렬에 안 쓴다. `start`(쿼리 파라미터, 기본 0)로 다음 페이지 검색. 관심사 id가 없으면 404

```
GET /interests                       → {"interests": [...]}
DELETE /interests/{interest_id}      → {"interest_id", "action": "deleted"}  (없으면 404)
POST /interests/{interest_id}/refresh
{ "existing_candidates": [...] }     # 이전 /search 응답을 그대로 되돌려보냄
→ {"recommended": [...]}             # 기존 후보 재스크리닝(관련 있는 것만) + 새 페이지 검색을 합쳐 반환
```

- `refresh`는 관심사를 수정한 직후 프론트가 호출한다 — 기존 후보를 버리지 않고 수정된 기준으로 다시 판정해 재활용한다(`paper_recommend.refresh_for_interest()`).

```
GET /interests/{interest_id}/papers?only_relevant=false   → {"papers": [...]}
```

- 이 관심사에 대해 지금까지 판정된 논문 조회. 판정할 때마다 기록되므로 검색 세션이 끝난 뒤에도 "이 관심사에 무엇이 추천됐는지" 다시 볼 수 있다. 관련 없다고 판정된 것도 기본으로 포함(`only_relevant=true`로 관련 있는 것만). 관심사 id가 없으면 404

```
POST /papers  (multipart/form-data: file, doi?, arxiv_id?)
→ {"paper_id", "analysis_status"}

GET /papers?status=recommended|owned|dismissed   → {"papers": [...]}
```

- `POST /papers`(⑤ 업로드 재정의, 08-05)는 업로드 바이트를 `library/`에 써넣고(이름 겹치면 `_2`, `_3`... 접미사) `track_in_background()`로 넘긴다 — 매직바이트(`%PDF-`) 검증만 즉시(아니면 400), 실제 파싱·청킹·임베딩은 백그라운드. 진행 상태는 `GET /papers`가 반환하는 각 행의 `analysis_status`(`pending`/`analyzing`/`done`/`failed`)로 폴링해 확인한다. `GET /papers`는 카탈로그 전역 조회 — 관심사별로 보려면 위 `GET /interests/{id}/papers`를 쓴다.

```
GET /papers/{paper_id}/summary   → {"paper_id", "extraction": {...}, "from_cache", "generated_by", "tokens_used"}
```

- 논문 요약 조회 — 이미 만들어둔 게 있으면 즉시 반환(`from_cache: true`), 없으면 그 자리에서 생성(LLM 호출 1회). 미등록 paper_id는 404, 논문이 너무 길어 한 번에 못 읽으면 422. **요약을 고치는 엔드포인트는 없다** — 원본 PDF가 따로 있으니 잘못되면 다시 등록하면 된다.

```
GET /equipment                       → {"equipment": [...]}
POST /equipment
{
  "name": "오실로스코프",
  "purpose": "전기 신호의 시간에 따른 파형 관찰",
  "detail": "대역폭 100MHz, 2채널",
  "precautions": "입력 전압이 채널 최대 정격을 넘지 않게 프로브 감쇠 설정을 확인할 것",
  "update_existing_id": null
}
→ {"equipment_id": 1, "action": "created"}   (update_existing_id 지정 시 "updated", 없는 id면 404)

DELETE /equipment/{equipment_id}     → {"equipment_id", "action": "deleted"}  (없으면 404)
```

- 실험도구 저장소(`equipment.py`) — LLM 호출 없는 순수 CRUD로 `/interests`와 같은 계약이다.
- **수정 시 안 보낸 필드는 건드리지 않는다**: `purpose`/`detail`/`precautions`의 기본값이 `""`가 아니라 `null`(= 명시 안 함)이라, 이름만 고쳐 보내도 등록해둔 주의사항이 지워지지 않는다. 값을 실제로 비우려면 `""`를 명시적으로 보내면 된다.
- `precautions`는 연구 워크플로우가 읽는다 — 실험 설계에 이 장비 이름이 등장하면 주의사항을 안내문(`comment`) 맨 앞에 붙인다.

```
GET /notes                           → {"notes": [{"id","title","text","created_at","updated_at"}, ...]}
POST /notes
{ "title": "파인만 8장 요점", "text": "확률론적 해석의 핵심은...", "update_existing_id": null }
→ {"note_id": 1, "action": "created"}   (update_existing_id 지정 시 "updated", 없는 id면 404)

DELETE /notes/{note_id}              → {"note_id", "action": "deleted"}  (없으면 404)
```

- 지식 노트(`knowledge_notes.py`) — `/equipment`와 같은 계약(`title`/`text` 기본값이 `null`이라 안 보낸 필드는 안 지워짐). 본문은 그대로 저장되고, 검색용 색인은 `text`가 바뀔 때만 다시 만든다(`title`만 바꾸면 재색인 안 함).

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

- **[docs/RoadMap.md](docs/RoadMap.md)** — 날짜별 개발 이력(완료), 라이브 검증 체크리스트, 예정 전체. 설계 노트·열린 질문·방향성 메모 포함
- **주차별 회고** — [README_08](docs/README_08.md)(LangGraph 에이전트) · [README_09](docs/README_09.md)(QLoRA 파인튜닝·평가) · [README_10](docs/README_10.md)(서버 관찰) · [README_11](docs/README_11.md)(Docker·EC2·CI/CD) · [README_12](docs/README_12.md)(CI/프론트엔드 정비·아키텍처 개편·논문 요약기 완성) · [README_13](docs/README_13.md)(라이브러리 표면 1차·실험도구·연구 워크플로우·EC2 배포 트랙 폐지)

> **기능이 왜 지금 모습이 됐는지**(초기 구상에서 바뀐 것, 버린 대안, 겪은 문제)는 이 README가 아니라 위 두 곳에 있다. 이 문서는 "지금 무엇이 있고 어떻게 쓰는가"만 다룬다.

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
- `pymupdf` + `pymupdf4llm` — PDF 파싱(마크다운 변환, `pdf_parse.py` 뒤에 격리). AGPL-3.0 듀얼 라이선스 — [docs/RoadMap.md](docs/RoadMap.md) "PDF 파싱 라이브러리 선택" 참고
- `pydantic` — 구조화 출력·State 스키마
- `fastapi` + `uvicorn` — REST API
- `langsmith` — tracing·평가
- `pytest` — 유닛 테스트 (dev 의존성, [테스트](#테스트) 참고)
