# RoadMap

물리 연구 어시스턴트 챗봇의 개발 이력과 계획. 상세 회고는 [README_08.md](README_08.md), [README_09.md](README_09.md), [README_10.md](README_10.md), [README_11.md](README_11.md) 참고.

## ✅ 완료

| 날짜 | 항목 | 내용 · 성과 |
|---|---|---|
| ~06-29 | LangChain RAG 파이프라인 (7주차) | LCEL 체인으로 파인만 강의록 RAG 구축 — 이후 LangGraph 마이그레이션의 출발점 |
| 06-29~07-04 | LangGraph 마이그레이션 + Self-RAG 에이전트 (8주차) | `StateGraph`로 retrieve→generate→verify 루프, 3방향 조건 분기(재생성/재검색/종료), try_count·limit 강제 종료. FastAPI `POST /query` 래핑 |
| 07-04 | 모델 선택 + fallback | `model_map`(gemini/claude) 요청별 선택, rate limit 시 자동 전환. verify는 생성과 다른 모델로 (교차 검증) |
| 07-05 | 로컬 임베딩 전환 | gemini 임베딩 → BAAI/bge-m3 (HuggingFace 로컬). rate limit·비용 제거, 파인만 전체 인코딩 완료 |
| 07-06 | 독립 리포지토리 분리 | 과제 레포에서 Science_Chatbot으로 이전, 주차별 회고를 docs/로 분리, 아키텍처 다이어그램 추가 |
| 07-10 | tool 노드 분리 (ReAct 그래프화) | generate 내부 while 루프 → `run_tools` 노드 + 조건 엣지. `messages: Annotated[list, add_messages]` 도입. LangSmith 트레이스에 tool 라운드 가시화, 추후 `interrupt_before` HITL 기반 마련 |
| 07-10 | tool 예외처리 + 서킷 브레이커 | 모든 tool_call에 ToolMessage 응답(실패 포함) → LLM 자가수정. 빈 결과/호출 실패/미등록 tool 3종 구분, 연속 2회 실패 시 해당 런에서 자동 제외, 결과 4000자 제한 |
| 07-12 | Pydantic State 전환 | TypedDict → BaseModel. 필드 기본값·`Literal` 검증으로 `.get()` 누락 버그 원천 차단 |
| 07-12 | 평가 데이터셋 구축 | eval.json 31문항 (7개 물리 카테고리 + 미해결 문제, 난이도 태그) / train_qa.json 45문항 (학습·평가 분리). 미해결 문항은 "미해결 인정 + 사실 정확성" 별도 채점 기준 |
| 07-11~13 | Qwen2.5-1.5B QLoRA 파인튜닝 (9주차) | Colab + Unsloth, r=16, 45문항 6에폭, loss 3.51→0.21. PTQ 비교(fp16/int8/int4) 후 Q4_K_M GGUF(941MB) 변환 |
| 07-13 | 모듈 분리 | `models.py`(model_map+fallback) / `tool.py`(레지스트리) / `retrieval.py`(임베딩+벡터스토어, ingest와 공유해 임베딩 모델 불일치를 구조로 방지) |
| 07-13 | site 제한 검색 tool 팩토리 | `make_search_tool` 클로저 팩토리로 wikipedia/arxiv site 제한 검색 생성 (`site:` 쿼리 주입) |
| 07-14 | 자체 모델 서빙 통합 | GGUF를 llama-server(OpenAI 호환 로컬 서버)로 서빙, `model_map["Qwen-tuned"]` 등록. 반복 루프 대응 `frequency_penalty=0.3`, `max_tokens` 제한 |
| 07-14 | fallback 후 교차 검증 버그 수정 | `generated_by`(실제 생성 모델)와 `disabled_models`(요청 내 고장 목록) State 추적 분리. verify는 생성자 회피 → 후보 소진 시 차순위(자가 검증) → 전 모델 소진 시 verify 생략 브랜치 |
| 07-14 | 장애 복원력 실증 | llama-server 다운 + gemini 쿼터 소진 이중 장애에서 2단 fallback·서킷 브레이커·차순위 검증 전 경로 정상 동작 확인 |
| 07-14~15 | 평가 시스템 + 비교 실험 | evaluate.py `--target`/`--name` 선택, judge는 claude-haiku 고정(채점자 일관성), results/에 실행별 저장, eval_avg.py 비교. **bare Qwen 0.132 → graph+Qwen 0.445** (단 verify=claude 영향 큼: verify까지 Qwen이면 0.176) / claude 0.905 vs graph(claude) 0.813 → 프롬프트 개선 후 0.827 |
| 07-15 | graph claude 고정 재실험 + judge temp=0 | gemini 혼입 제거하고 재측정: graph(claude) 0.910 vs bare 0.915 — 차이가 "측정 문제" 단일 문항으로 좁혀짐. 근접-오검색(인접 주제 문서가 더 위험) 가설 도출 |
| 07-15 | verify 판정 기준 수정 | fix_needed는 사실 오류만(문서 근거성 아님), verify에 comment 배출구 추가 — "정확하다면서 반려"로 3라운드 낭비 + 프리앰블 유발하던 연쇄 차단 |
| 07-15 | 출력 이원화 (answer/comment) | 사용자에겐 둘 다, 평가는 answer만. final_answer 노드에서 재시도 케이스만 structured 분리(평시 추가 호출 0), 시스템 comment(limit 도달·fallback 고지)는 코드가 작성. limit 실패 실전 케이스에서 "정직한 실패" 고지 확인. 추출자는 generated_by 유지 결정(토큰 절약 목적 존중) |
| 07-15 | **최종 재평가 — bare 역전** | 수정 전부 반영한 graph(claude 고정) **0.926 > bare claude 0.915** — 파이프라인이 강한 모델도 개선함을 최초 확인 (electromagnetism 0.700→0.943, open_problem 0.707→0.907). 단일 실행이라 신뢰도 단서 있음, 반복 실험은 예정 |
| ~07-19 | 10주차 과제 — 서버 관찰 | 유닉스 명령어로 서버 프로세스·스레드·메모리 분석 + WireShark로 /query HTTP 통신 캡처 — 평문 노출 직접 확인 (README_10.md) |
| 07-20 | **단기기억 + 쓰레드** | MemorySaver checkpointer + thread_id(FastAPI 필드, 미지정 시 uuid). **reset_turn 노드**로 턴 경계 확립(messages만 보존, 임시 상태 전부 초기화) + generate 질문 등록 조건을 try_count 기준으로 교체. verify에 모호 질문 명확화 기준 추가, tokens_used 추적 추가 |
| 07-21 | 11-1. Docker 패키징 + Compose | Dockerfile(uv, `uv sync --frozen`으로 uv.lock 그대로 재현, 레이어 캐싱용 2단계 분리) + docker-compose.yml(science-chatbot / llama-server 분리, `profiles`로 llama-server 선택 실행, 서비스명 기반 컨테이너 간 통신). 로컬 실행 검증 완료 (README_11.md) |
| 07-21~22 | 11-2. EC2 배포 + 외부 접근 | Docker Hub 경유 → `t4g.micro`(arm64 일치) pull·실행, 보안그룹 8000 오픈. 프리티어 RAM 1GB에서 bge-m3 로드 시 OOM(Exited 137) 실제 재현 → 스왑 2GB로 해결. 외부 접근까지 검증 |
| 07-22 | 11-3. GitHub Actions CI/CD | `main` push 시 자동 빌드(arm64 러너)→Docker Hub push→EC2 SSH 배포. 시크릿은 GitHub Secrets. 두 번의 실패(SSH timeout, PAT scope 거부)를 에러 메시지 정독으로 진단·해결 (README_11.md) |
| 07-22~23 | 이미지 경량화 (CPU 전용 torch) | 8.77GB 이미지 원인이 `sentence-transformers`가 끌어온 미사용 CUDA/nvidia 패키지(2GB+)임을 빌드 로그로 특정. `pyproject.toml`에 `[tool.uv.sources]`로 torch를 PyPI CPU 인덱스(`download.pytorch.org/whl/cpu`)에 고정 → nvidia 19종 제거, torch `2.13.0+cpu`로. **이미지 8.77GB → 2.04GB**. EC2 디스크 99%→63% 회복. GHA `type=gha` 캐싱은 400MB 청크 제한+buildkit 이슈로 포기(README_11 §5.2) |
| 07-23 | 테스트 게이트 | pytest 톨게이트 유닛 테스트 4종(`route_by_fix`/`reset_turn`/`_add_tokens`/`invoke_with_fallback`, 전부 실제 API·벡터DB 없이 1~2초) + `tests/conftest.py`(retrieval import-time 로딩 차단, API 키 더미값, `make_state` fixture). `deploy.yml`을 `test`→`deploy` job으로 분리해 테스트 실패 시 배포 자체가 안 나가도록 게이트 연결, 배포 스크립트에 `docker image prune -f` 추가. 실제 push로 test→build+push→EC2 배포 전체 파이프라인 검증 완료 (README_11.md §8) |
| 07-23 | 프론트엔드(Streamlit) + 배포 자동화 | 채팅 UI를 백엔드와 완전 분리된 서브프로젝트(`frontend/`, 별도 이미지)로 구축, `docker-compose.yml`에 `profiles: ["frontend"]`로 선택 설치 연결. `deploy.yml`에 프론트 이미지 빌드+push, `docker-compose.yml` EC2 자동 전송(`appleboy/scp-action`), `--profile frontend`로 배포까지 통합 — git push 한 번으로 백엔드+프론트 전부 자동 배포. 겸사겸사 verify가 대화 이력(단기기억)을 못 보던 버그 발견·수정 + 턴 종료 시 메시지 정리(`RemoveMessage`) 추가 (README_12.md) |
| 07-24 | **아키텍처 개편 — 표면/능력/데이터 3층** | "슈퍼바이저가 7개 에이전트를 라우팅하는 단일 챗봇" → 표면(메인 챗/연구 워크플로우/추천 피드) · 능력(호출당하는 서브그래프) · 데이터 서비스 3층으로 재설계. 상시 챗봇은 메인 챗 하나, 추천(③)은 cron 파이프라인, 논문 분석기(②)를 허브 능력으로 최우선 구축. 예정 순서 전면 재편 (README §목표 아키텍처, README_12 §7) |
| 07-24 | 물리 QA 서브그래프 포장 (6-1) | `graph.py`를 checkpointer 없는 순수 능력으로 분리 — `reset_turn` 노드는 fresh invoke 자체가 Pydantic 기본값으로 이미 초기화라 통째로 불필요해져 삭제(당초 "부모로 이동" 계획보다 더 단순해짐). `orchestrator.py` 신설: `ParentState`(question/answer/comment/model/tokens_used/disabled_models/messages) + `physics_qa_node` 래퍼(능력을 fresh invoke하고, 새로 생긴 메시지만 슬라이싱해 반환 — `add_messages`가 id 기준 병합이라 안 그래도 중복은 안 되지만 매 턴 불필요한 교체 시도를 피함). checkpointer는 이제 orchestrator 소유. `main.py`가 orchestrator를 호출하도록 전환, `top_k`/`limit`은 능력 내부 다이얼이라 API에서 제거. mock 모델로 멀티턴 스모크 테스트 검증(메시지 중복 없이 정상 누적) |
| 07-27 | effort 프로필 (low/medium/high) | top_k/limit은 능력 내부 다이얼이라는 판단은 유지, 그 위에 Claude reasoning effort와 같은 패턴으로 사용자 노출용 프로필만 추가. `graph.py`의 `EFFORT_PROFILES`(dict) + `model_validator`로 숫자 매핑 캡슐화, `orchestrator`/`main`/프론트는 이름만 통과. 죽어있던 프론트 top_k 슬라이더를 effort 선택박스로 교체 |
| 07-27 | 스트리밍/진행상황 API + comment·트레이스 분리 (6-2) | 래퍼 함수 노드 패턴상 부모(orchestrator) 레벨 `stream_mode`로는 능력 내부 진행상황이 안 보여서, `physics_qa_node`가 능력을 `stream(stream_mode="values")`로 순회하며 `get_stream_writer()`로 부모의 `stream_mode="custom"`에 실어 보냄. `main.py` `/query`가 `astream`+SSE로 전환. 스트리밍하다 comment가 사용자용/디버그 트레이스 역할을 겸하던 문제 발견 — `State`에 `trace`(내부 로그) 신설, `comment`는 verify의 구조화 출력(`answer.comment`)만 담도록 분리 |
| 07-27 | arxiv API 이슈 해결 (6-3 선행) | `langchain_community`의 `ArxivQueryRun`이 arxiv.org 서버 이슈+구버전 API 요구로 막혀있던 것을, `arxiv_api.py` 신설로 해결 — export.arxiv.org의 공식 API를 `requests`로 직접 호출·Atom XML 파싱해 제목/저자/연도/arxiv id/요약을 구조화된 dict로 반환(새 의존성 없음). `tool.py`의 `search_arxiv` tool이 이걸 감싸 물리 QA의 tool-calling 루프에 사용(기존 DDG `site:arxiv.org` 우회 대체), 원본 `arxiv_search()` 함수는 6-3 논문 분석기가 그대로 재사용할 예정 |

## 🔄 진행 중

| 날짜 | 항목 | 상태 |
|---|---|---|
| 07-15~ | 베이스라인 완주 | gemini 쿼터 리필 대기 — bare gemini, graph(gemini-only)에서 역전 재현 확인 후 전체 비교표 완성 |

## 📅 예정

| 목표 시기 | 항목 | 내용 |
|---|---|---|
| 08-03 | 논문 분석기 (②) — 허브 능력 | abstract 트리아지 → 전문 요약·평가 → 논문 요약 VDB 저장. **메타데이터에 서지정보(제목·저자·연도·arxiv id) 포함** — 참고문헌 인용 포맷(BibTeX 등)의 전제. ③④⑦이 전부 재사용하므로 최우선. 선행 조건(arxiv API 이슈)은 07-27에 해결 완료 — `arxiv_api.py`의 `arxiv_search()`를 그대로 재사용. ② 완성 직후 QA(④)에 "참고" 부착(retrieve 문서 메타데이터, 추가 호출 0)이 거의 자동으로 생김 |
| 08-05 | SqliteSaver 영속화 | MemorySaver는 재시작 시 소멸 → 디스크 영속화. **HITL보다 먼저** — interrupt로 멈춘 승인 대기 상태가 재시작에 살아남아야 함. `/query` 응답에 interrupted 상태 + resume 엔드포인트 API 설계 포함 |
| 08-07 | 관심사 서비스 (①) | 관심사 저장소(VDB 컬렉션) + 문서 작성기 능력(대화 → 템플릿 문서, 유사도 중복 검사 → 기존 편집 제안, 등록 확인 `interrupt`) + 턴 종료 후 훅("대화 내용을 관심사로 등록할까요?" — 싼 모델 1회 판정). 작성기는 ⑤ 실험도구와 템플릿만 갈아끼워 공용 |
| 08-09 | 추천 검색 (③) + 논문 카탈로그 | ③: **관심사에서 트리거할 때만** 실행 (cron 아님) — 관심사 기준 검색 → ②로 평가 → 랭킹 → 카탈로그에 recommended 기록. 논문 카탈로그(SQLite, DOI 기본 키, `status: recommended/owned/dismissed`) — 등록 시 DOI 매칭으로 recommended → owned 전환(추천에서 내려감). 권위 논문 목록(인용수 기반)도 관심사별 조회·캐시. **검색·평가 내부를 공용 함수로 분리**해 참고문헌 추천기와 공유(추천기는 문맥 기반 온디맨드, QA 풀 호출은 라우터 분기) |
| 08-11 | 라이브러리 표면 1차 | 관리 UI 통합 화면(Streamlit multipage) — **논문 탭**(PDF·DOI·arxiv id 등록 → ② ingest, 카탈로그 상태 표시. 등록의 주 경로) + **관심사 탭**(카드별 보유/추천/권위 논문 목록, "지금 검색" 트리거). 실험도구 탭은 ⑤와 함께, 지식 노트 탭(`source_type: user_note` 신뢰도 구분)은 후속. **프론트 스택 재검토 겸행** — 표면 4개엔 Streamlit 한계, React 등 전환 검토 |
| 8월 중 | 피드 표면 | 관심사와 무관하게 hype 소식 cron 크롤링 → 키워드 태깅 → 관심사 일치 키워드 색 강조 + 상단 정렬. 추천 검색과 별개(피드는 싸고 넓게, 추천은 비싸고 깊게) |
| 08-10 | 메인 챗 라우터 | QA / 문서 작성기 호출 / 추천 조회 3~4갈래 얇은 라우터 (거대 슈퍼바이저 아님). **후속 질문 재작성 통합** — 라우팅 결정과 "에이전트에 넘길 정제된 task"를 structured output 한 번에. 라우팅 정답 평가셋(10~20문항)도 함께 구축 |
| 08-12 | 장기기억 | VDB 메타데이터 필터링으로 user_id 태그 — 유저별 LTM 분리, 검증된 문헌의 LTM 승격. `disabled_models`도 부모 State 공유로 전환(쿼터 소진을 에이전트마다 재발견하지 않게) |
| 08-13 | 메시지 트리밍 | 멀티턴에서 messages 무한 성장 → 긴 대화의 generate 비용 관리 (tokens_used로 성장 측정 가능) |
| 8월 중 | verify 구성 비교 실험 확장 | self / 교차 / 무 verify / 다중 모델 앙상블 — correctness·토큰·지연 지표로 체계화 (현재 부분 진행: Qwen self-verify vs claude-verify 완료). **bare vs graph 0.915 vs 0.926 차이의 반복 실행 신뢰도 검증(3회 이상 평균)**도 함께 진행 |
| 8월 하순 | 실험도구 DB (⑤) + 연구 워크플로우 (⑥) | 장비 spec 구조화 레코드(+선택적 임베딩), 문서 작성기 재사용. 가설 수립 → 실험 설계(Plan-and-Execute) → 실험 운영을 별도 표면(단계형 화면)으로. 안전 가드레일 `interrupt_before` HITL — 재실험 루프는 실험 설계만 재호출. **각 단계가 참고문헌 추천기를 호출해 워크플로우 공유 references 목록에 누적**(서지 + 인용 이유 + 추가 단계) — 가설(배경)·설계(방법론)·운영(결과 비교) |
| 8월 하순 | 논문 작성 능력 (⑦) | 실험 결과·사용자 문서 기반 초안 → ②로 자체 검토 → 재작성 (Evaluator-Optimizer, 검증된 패턴 재사용) + 번역 레이어(후처리 노드). **워크플로우가 누적한 references 목록을 소비**해 인라인 인용·참고문헌 생성 — 목록에 없는 인용은 환각 신호로 자체 검토에서 반려 |
| 이후 | 외부 논문 API 어댑터 | 유료 저널 대응 — Crossref(ISSN별 신착 감지), Unpaywall/CORE(OA 본문 확보), OpenAlex(인용수·권위 논문). **검색 함수 뒤의 구현 세부라 마지막에 갈아끼움** — 그 전까지는 arxiv·웹 검색으로 전 기능 완성 |
| 이후 | tool 정비 | wikipedia-api 기반 커스텀 tool(wikipedia 패키지 신뢰성 문제 대체), WolframAlpha 수식 검증 tool |
| 이후 | tool 예외처리 잔여 | (핵심 제약·실패 3종 구분·서킷 브레이커·라운드 카운트·결과 길이 제한은 `run_tools`에 구현됨) **타임아웃**(네트워크 tool hang 대비 wrapper 레벨 제한), **관측성**(`tools_used`·`tool_errors` State 기록 → 디버그+verify 비교 지표), **보안 인지**(웹 검색 결과 프롬프트 주입 — 가드레일과 함께 처리) |
| 이후 | 학습 데이터 확장 | 45문항 → 파인만 강의록에서 대량 생성, 한국어 혼입(중국어 토큰) 대응, 데이터 비율 실험(논문 문어체 vs 평서문) |
| 이후 | 개인 모델 2차 학습 | 확장 데이터로 재파인튜닝 → 젬마 등 가중치 공개 모델과 비교 평가 |

> 날짜 규칙: 완료 항목은 커밋 기준, 예정 항목은 착수 시 목표 시기를 채우고 완료 시 ✅ 표로 이동.

---

## 설계 노트 · 열린 질문

**아키텍처 개편 결정 (07-24)** — "단일 슈퍼바이저 챗봇 vs 서비스별 챗봇 분리" 논의의 결론:

- 문제의식: 한 챗봇에 7개 기능을 뭉치면 기능 구분이 안 되고 사용자가 헷갈림. 그렇다고 서비스별 챗봇 7개로 쪼개면 사용자가 어느 봇에 물을지 스스로 라우팅해야 하고(관심사·논문·추천에 걸치는 질문 존재), thread/메모리/프론트엔드가 봇 수만큼 복제됨
- 결론: 챗봇을 쪼개는 게 아니라 **작업 성격에 맞는 UI 형태를 매칭** — 대화는 챗, 추천은 피드, 등록은 폼+어시스트, 연구는 단계형 워크플로우. 기능들은 표면(3개) / 능력(호출당하는 서브그래프) / 데이터 서비스(CRUD)로 층을 나눔
- 결과: 그래프는 3개(챗, 연구 워크플로우, 추천 파이프라인)로 수렴, 오케스트레이터는 "만능 슈퍼바이저"에서 "표면별 얇은 라우터"로 축소, 추천(③)은 그래프에서 빠져 cron이 됨. 데이터 층 공유로 맥락 단절 없음, 능력 단위로 독립 평가 가능(기존 evaluation 철학과 일치)
- 상세: README §목표 아키텍처, README_12 §7

**설계 확장 (07-24, 2차)** — 표면 4개 체제:

- 피드 ≠ 추천: 피드는 관심사 무관 hype 소식(cron·키워드 태깅·관심사 일치 시 색 강조+상단 정렬), 추천 검색은 관심사 트리거 온디맨드. 논문 카탈로그(DOI 기본 키, 상태 recommended/owned/dismissed)로 "등록하면 추천에서 내려감" 구현
- 라이브러리 표면 신설: 관심사·논문·실험도구·지식 노트 관리를 탭 하나의 화면으로 통합 (파편화 방지). 논문 등록의 주 경로는 라이브러리, 메인 챗은 보조
- 지식 노트: 사용자 지식체계를 RAG에 포함하되 `source_type: user_note`로 신뢰도 층 분리 — verify 오염 방지
- 외부 API(Crossref·Unpaywall·OpenAlex)는 마지막에 붙이는 어댑터 — API 연결이 목표가 되지 않게, 초기엔 arxiv·웹 검색으로 완성
- 프론트 스택: 표면 4개엔 Streamlit 한계 — 라이브러리·피드 구축 시점에 React 등 전환 검토

**멀티 에이전트 전환 전 사전 점검 (07-24 리뷰)** — 6-1 착수 전 반영할 것:

- 서브그래프 포장은 래퍼 함수 노드 방식(State 비공유) — 컴파일된 그래프 직접 삽입 시 `messages` reducer 공유로 부모 이력이 오염되고 `final_answer`의 RemoveMessage가 부모까지 건드림
- checkpointer는 부모로 (서브그래프는 부모 checkpointer 상속), reset_turn도 부모 소속 — 한 사용자 턴에 같은 능력이 여러 번 호출될 수 있음
- HITL 전에 SqliteSaver — interrupt 대기 상태가 재시작에 살아남아야 하고, resume API 설계도 필요
- comment 채널 분리 — 사용자용 comment와 디버그 트레이스 혼재 상태로 능력이 늘면 폭발. 트레이스는 LangSmith 몫
- verify()의 "차순위도 실패→검증 생략" 분기 `disabled_models` 리셋 버그 (To Do 참고)

**Evaluator-Optimizer Pattern 효율성 의문** (꼬리 질문 체인):

- verify용 고급 검색을 어차피 한 번 하면, 처음부터 고급 검색으로 답하면 안 되나?
- vs 그러면 같은 context로 생성·검증 → "같은 책 읽은 바보가 바보를 검증"?
- verify만 좋은 모델? vs 그럴 거면 생성부터 좋은 모델?
- generate/verify 다른 모델? vs 처음부터 여러 모델 앙상블?

**멘토 답**: 관통하는 것은 "실험". "낫다"의 평가 기준을 수립한 뒤 각 가설(설정)을 실험해 비교하라. 개인 프로젝트에 이 실험·결과 분석이 스토리텔링으로 담기면 매력적. 라우팅 전략: 쉬운 일에 가벼운 모델 배치로 토큰 절약 가능(고급 모델은 토큰 단가 자체가 높음).

**→ 실험 설계** (예정 08-08과 연결): eval.json 31문항(카테고리·난이도 태깅, 미해결 3문항 포함) 기준으로 구성 비교 — (a) 단일 모델 self-verify (b) 교차 모델 verify(현재) (c) verify 없이 처음부터 고급 모델/고급 검색 (d) 다중 모델 종합. 지표: correctness 점수, 총 토큰, 지연시간.

**nginx 도입 재고 대상** (지금은 보류): Streamlit 앞에 nginx 리버스 프록시를 세우는 건 도메인 구입+HTTPS가 필요해지거나 공개 서비스화할 때 다시 검토. Streamlit은 WebSocket에 의존해서 nginx 기본 `proxy_pass`만으로는 안 되고 `Upgrade`/`Connection: upgrade` 헤더 설정이 추가로 필요함 — 지금은 도메인도 없고 혼자 쓰는 규모라 이 수고 대비 얻는 게 없음(포트 숨기기·TLS·다중 인스턴스 로드밸런싱 전부 현재 미해당).

**자체 서빙 엔진 (언젠가)**: 지금은 파인튜닝한 GGUF를 llama-server(기존 서빙 엔진)에 맡기고 있는데, 토크나이징·배칭·KV 캐시 등 추론 서빙을 직접 구현해보고 llama-server(원본) 대비 정확도·속도를 evaluate로 비교. 제품 요구사항이 아니라 "에이전트 서빙(운영)" 학습 목적 — 아래 방향성 메모와 연결.

## 방향성 메모

- 자기 챗봇 개선에만 집중하지 말고, 여러 기능을 써보며 공부에 활용: 챗봇 → RAG → 에이전트
- 멀티 **에이전트 개발**, **에이전트 서빙**(운영, → 자체 서빙 엔진 실험), 모델 튜닝은 할 줄 알아야
- 프레임워크 암기 X — 만들고자 하는 시스템을 어떻게 만드는지 참고 정도
- 바닐라 버전 / LangChain 버전 분리 유지 ("바닐라로 여기까지 했다")
