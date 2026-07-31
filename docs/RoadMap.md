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
| 07-28 | **논문 처리 3분할 결정** (6-3 착수 전) | 기존 ②("abstract 트리아지 → 전문 요약·평가")가 성립하지 않는 파이프라인이었음을 확인 — 유료 저널은 트리아지를 통과해도 전문을 못 읽고, 보유 논문은 이미 선별이 끝나 트리아지가 불필요. 입력·비용·호출자가 다르므로 **논문 요약기(②a, 보유 논문 전문·lazy) / 논문 스크리닝(②b, abstract+지표) / 논문 검색 어댑터**로 분리. 등록 시 인코딩과 요약 생성 분리, 권위 판단은 LLM이 아니라 지표 계산으로. 6-3 범위가 ②a로 축소되고 ②b는 ③(08-09)과 함께 |
| 07-27 | tool 라운드 예산 낭비 버그 수정 | 실전에서 `search_arxiv` 연속 2회 실패로 서킷 브레이커 발동 후, LLM이 그 사실을 모르고 3회차에 같은 tool을 재요청 → `[사용 불가]`로 거부됐는데 이 거부까지 `tool_rounds`를 소모해버려서, 정작 fallback tool(`duckduckgo_search`)은 `MAX_TOOL_ROUNDS=3` 한도 초과로 시도조차 못 해본 채 끝난 사례 발견(verify는 "정직한 실패 인정"으로 통과했지만 구조적으로 fallback이 항상 막히는 상태였음). `run_tools()`에 `attempted` 플래그를 추가해 `[한도 초과]`/`[사용 불가]`처럼 실행을 시도조차 안 한 거부는 라운드로 안 세도록 수정 — 전역 라운드 캡 자체는 유지(tool별 연속실패 카운터만으로 대체하면 여러 tool을 번갈아 실패하는 라운드-로빈 패턴에서 무한루프 방지가 안 됨) |
| 07-28 | 논문 요약기(②a) 전문 처리·오케스트레이션 완성 | `pdf_parse.py`(PyMuPDF 어댑터)·`paper_chunking.py`(헤더 분할+병합, `is_references` 태깅, 임베딩용 `split_for_embedding` 별도 함수)·`paper_id.py`(DOI/arXiv/해시 우선순위 정규화)·`paper_extraction.py`(구조화 추출 스키마 — 품질 판정 아님)·`models.py`(`CONTEXT_BUDGET_CHARS`/`check_context_budget`)를 `paper_ingest.py`(`register_paper()`+`get_paper_summary()`)로 통합. `retrieval.py`에 별도 `papers_vectorstore`(컬렉션 분리, `doc_type: fulltext_chunk/summary`) 신설, `graph.py`의 `retrieve()`가 이 컬렉션도 같이 검색해 QA에 논문 참고를 추가 호출 없이 붙임. 실제 14페이지 논문으로 등록(122청크)+요약 생성까지 스모크 테스트 확인. 요약 생성은 "단순 경로부터" 원칙대로 map-reduce 없이 한 번에 호출 + 예산 초과 시 정직한 실패(`ContextBudgetExceeded` 그대로 전파) — 재귀 분할은 실제로 걸리는 사례를 만나면 착수. 카탈로그(SQLite)는 의도적으로 미포함(6-6 몫), 지금은 Chroma 메타데이터가 등록 여부의 유일한 기록 |
| 07-28 | 테스트 정리 + CI를 PR 게이트로 확장 | 61개 테스트 중 실질 검증이 없는 2개 제거(SHA-256 자체의 성질을 재확인하던 해시-차이 테스트, 타입만 확인하던 tautological 테스트) + 코드에서 이미 "문단→줄" 용어를 바꾼 데 맞춰 테스트 함수명도 재정렬. `.github/workflows/test.yml`을 재사용 워크플로우(`workflow_call`)로 분리해 `pull_request`(main 대상)에도 직접 트리거 — 지금까지 테스트는 `deploy.yml`이 push(main)에만 붙어 있어 PR 단계에선 안 보이고 merge 이후(배포 직전)에야 실패가 드러났음. `deploy.yml`의 test job은 이제 `uses: ./.github/workflows/test.yml`로 재사용만 하고 pytest 스텝은 한 곳에만 유지 |
| 07-28 | 6-3 마무리 — 요약 부재 시 백그라운드 생성 | `paper_ingest.py`에 `ensure_summary_in_background()` 신설 — 캐시된 요약이 없으면 daemon thread로 `get_paper_summary()`를 실행하고 즉시 반환(이번 턴을 안 막음), 모듈 전역 in-flight 집합으로 같은 논문의 중복 생성 방지. "전문 청크로 답한다" 쪽은 별도 코드 불필요(요약 문서가 없으면 유사도 검색이 애초에 `fulltext_chunk`만 반환). `graph.py`의 `retrieve()`가 검색된 논문 중 요약 없는 것들을 감지해 트리거하고 trace에 기록. 완료를 실시간 통지하는 채널은 안 만듦 — 다음 조회 때 캐시로 확인되는 것 자체가 결과(단순 경로부터). 실제 스레드 기동(`_spawn_background`)만 분리해 테스트에서 동기 실행으로 갈아끼울 수 있게 함. 이걸로 6-3 범위(의도적으로 보류한 map-reduce reduce·헤더 폴백·라이브러리 UI 제외) 완료 |
| 07-28 | 논문 파이프라인 디렉토리 정리 | 5개 모듈(`pdf_parse`·`paper_chunking`·`paper_id`·`paper_extraction`·`paper_ingest`)을 `paper/` 패키지로 이동 — `retrieval.py`·`arxiv_api.py`는 물리 QA·논문 요약기·추천 등 여러 표면이 공유하는 인프라라 루트에 유지. `paper_sections.py` → `paper_chunking.py` 개명(헤더 기반 분할과 임베딩용 청킹 두 기능을 모두 만드는 모듈이라 '섹션'보다 '청킹'이 목적에 맞음) |
| 07-28 | 논문 파이프라인 1차 리뷰 대응 | 서지 메타데이터 화이트리스트(`_BIBLIOGRAPHIC_WHITELIST`: title/authors/year/arxiv_id/pdf_url)로 abstract 등 긴 필드가 청크 수만큼 그대로 복제되던 문제 수정. 백그라운드 요약 생성 모델을 그 턴의 `state.model`이 아니라 고정 상수 `BACKGROUND_SUMMARY_MODEL`로 분리(요청 모델과 무관하게 예산이 가장 넉넉한 모델 사용) + `ContextBudgetExceeded`(재시도해도 항상 같은 이유로 실패)를 `_PERMANENTLY_FAILED` 집합에 영구 기록해 매 조회마다 스레드 재기동 방지, 이 체크를 DB 조회(`_fetch_summary`)보다 먼저 하도록 순서 변경(무료 검사 우선). `_fetch_summary`의 안전하지 않은 dict 접근(KeyError 위험) 수정. `parse_pdf`를 경로 대신 바이트 인자로 바꿔 해시(`normalize_paper_id`)·파싱이 같은 파일을 두 번 안 읽게 하고, 스캔 여부 판정도 전체 페이지 순회 대신 앞 5페이지 샘플링으로 축소 |
| 07-28 | retrieve() 점수 병합 + 논문당 청크 상한 | 이전엔 feynman·papers 컬렉션에서 각각 k개씩 가져와 이어붙여 논문 등록 이후 항상 최대 2k개가 context에 들어가던 버그 수정 — `similarity_search_with_score`로 두 컬렉션 후보를 점수(L2, 작을수록 유사) 기준 병합 후 상위 k개만 채택(top_k는 "컬렉션당"이 아니라 "총량"이라는 원래 의도 회복). 점수 병합만 하면 요약+전문청크 중복·`chunk_overlap`·반복 주장 등 3중 원인으로 논문 한 편이 k슬롯을 전부 차지할 수 있어 `MAX_CHUNKS_PER_PAPER=2` 상한을 추가(그리디 백필 — 상한에 걸려 빠진 자리는 다음 순위 후보가 채움, 빈 슬롯을 남기지 않음). "파인만 최소 1개 보장" 같은 컬렉션 쿼터는 의도적으로 안 둠 — 07-15에 발견한 근접-오검색을 반대 방향으로 재현하는 것이라 |
| 07-28 | References 판정 — 라벨과 분류 분리 | `paper_chunking.py`가 청크의 대표 헤더 라벨(표시용, 가장 깊은 헤더 하나만 기록)과 `is_references` 분류(References 섹션 소속 여부)를 같은 값에서 파생시키던 걸 분리 — "# References" 아래 "## Appendix A" 같은 하위 헤더가 있으면 대표 라벨이 "Appendix A"가 돼 정규식이 매치하지 않아 `is_references=False`로 잘못 분류되던 잠재 버그(코드 리딩 질문 중 발견) 수정. 분류는 헤더 계층 전체(`any(...)`)로 판정하고, 표시용 라벨은 기존대로 가장 깊은 헤더만 유지 — 대표성(라벨)과 소속 판정(분류)은 다른 요구라 하나의 값을 공유하면 안 됨 |

| 07-28 | 아키텍처 그림 갱신 + 이미지에 dev 의존성이 새던 것 수정 | `docs/draw_architecture.py`에 논문 처리 3분할(②a 요약기/②b 스크리닝/논문 검색 어댑터)을 반영하고, 굵은 테두리로 "구현 완료"를 표시하도록 추가(색은 이미 층 구분에 쓰고 있어 선 굵기로 축을 분리). 겸사겸사 발견 — `pyproject.toml`에 "배포용은 `--no-dev`" 주석을 달아뒀는데 정작 **Dockerfile의 `uv sync` 두 곳에 `--no-dev`가 빠져 있어 pytest가(그리고 이번에 추가한 matplotlib·pillow·fonttools까지) 운영 이미지에 계속 들어가고 있었음.** 두 줄에 `--no-dev` 추가 — CI는 러너에서 직접 `uv sync`+pytest를 돌리므로 테스트 게이트는 그대로 |
| 07-29 | 6-3b① abstract 확보 | 우선순위 `bibliographic["abstract"]`(arxiv) > PDF의 Abstract/초록 섹션(`paper_chunking.extract_abstract()` — 이미 계산된 `split_for_embedding()` 조각에서 헤더 매칭만, 재파싱·LLM 없음) > 없음. `doc_type="abstract"` 문서 1개로(청크 복제 없이) 저장 — `_store_summary()`와 같은 패턴. `_is_references_header`/`_is_abstract_header` 정규식에 한글 변형(인용문헌·참고자료·초록) 및 붙여쓰기 추가 |
| 07-29 | 답변 근거 표시 | `graph.py`에 `describe_context_sources()` 순수 함수 신설 — `state.context` 메타데이터만으로(LLM 판단 없이) "이번 턴에 참고 가능했던 자료"를 파인만/논문(제목+전문발췌·요약·초록 구분)/웹검색(tool 이름)으로 정리해 `final_answer()`가 `comment`에 "참고한 자료:" 로 첨부. "실제로 답변이 썼는지"가 아니라 "참고 가능했는지"만 표시(전자는 LLM 판단이 필요해 결정론 원칙과 충돌) — 아래 설계 노트 참고 |
| 07-29 | 논문 서지정보 보완 — summary title + arxiv 자동 조회 | (1) `_fetch_bib_meta()` 신설 — 이미 청크에 복제돼 있던 title 등을 꺼내 `_store_summary()`에도 넣음(summary 문서는 title이 없어 근거 표시에서 paper_id로만 보이던 문제). (2) `arxiv_api.py`에 `fetch_by_id()`(id_list 조회, 키워드 검색 아님) 신설, `register_paper()`가 arxiv_id는 있는데 bibliographic에 abstract가 없으면 자동 호출해 title·authors·year·abstract·pdf_url을 한 번에 채움(호출자 명시값 우선, 실패해도 등록은 진행) |
| 07-29 | 6-3b② 추출 프롬프트에 abstract 앵커 | `get_paper_summary()`가 저장된 abstract가 있으면 human 메시지를 `[논문 초록]\n{abstract}\n\n[본문]\n{full_text}`로 조립하고 시스템 프롬프트에 `ABSTRACT_ANCHOR_INSTRUCTION` 첨부 — "초록에 있는 주장도 core_claims에서 빼지 마라, 다만 한계·미해결·공개 여부는 초록에 보통 없으니 본문에서 찾아라". abstract 없으면 프롬프트 완전히 그대로(회귀 없음). `check_context_budget()`도 `full_text`가 아니라 최종 합친 텍스트로 검사하도록 수정(경계 케이스 정직성) |
| 07-29 | 6-3b③ 제목 검증 | `pdf_parse.py`의 `parse_pdf()`가 `pdf_title`(PDF 내장 메타데이터 우선, 없으면 마크다운 첫 줄 폴백)을 추가로 반환. 새 모듈 `paper/title_check.py`: `normalize_title()` + `classify_title_match()`(`difflib.SequenceMatcher`, 임계값은 실측 전 대략치)로 `match`/`notation_diff`/`different_paper`/`no_comparison` 4등급 분류. `register_paper()`가 등록 끝에 판정만 내려 반환값(`title_check`)에 실어 보냄 — **등록 자체는 막지 않는다**(당초 계획한 "파싱·검증→확인→저장" 2단계 등록 흐름은 라이브러리 UI(6-8)가 생길 때까지 보류, 지금은 1단계 그대로에 판정만 얹음) |
| 07-31 | 6-4 SqliteSaver 영속화 | `MemorySaver` → `AsyncSqliteSaver`(동기 `SqliteSaver`는 실제 소스 확인 결과 `astream()`에서 "does not support async methods"로 바로 예외 — `/query`가 `astream(stream_mode="custom")`을 쓰므로 비동기 필수). `AsyncSqliteSaver.from_conn_string()`이 비동기 컨텍스트 매니저라 요청마다 못 열고 서버 생명주기 동안 한 번만 열어야 함 → `orchestrator.py`는 컴파일 "전" `graph` 빌더 + `CHECKPOINT_DB_PATH`("data/checkpoints.sqlite")만 export하고, 실제 컴파일(체크포인터 연결)은 `main.py`의 FastAPI `lifespan`에서(`app.state.graph`에 보관, `/query`는 `request.app.state.graph` 사용). `data/` 디렉터리는 `docker-compose.yml`("./data:/app/data" 바인드 마운트) · `.gitignore`/`.dockerignore`(디렉터리 단위) 반영. **검증**: 별도 프로세스 두 번(재시작 흉내) 실행해 같은 thread_id로 "방금 뭐라고 답했는지 요약해줘"가 첫 프로세스의 답을 정확히 요약함을 확인 — 재시작 후에도 대화가 실제로 이어짐. `interrupted 상태 + resume 엔드포인트 API`는 범위에서 뺌(설계 당시 합의) — 실제 interrupt 사용처(08-07 관심사 서비스, 문서 작성기 등록 확인)가 생길 때 같이 설계 |

| 07-31 | 6-3b·6-4 코드 검사 + 지적 3건 수정 | 세션 작업분 전체를 훑어 3건 발견·수정(각각 **수정을 되돌려 테스트가 실제로 실패하는지 확인**한 뒤 커밋). **(1) `extract_abstract()`가 07-28 References 버그를 그대로 재현** — 조각의 대표 라벨(`header`, 가장 깊은 헤더) 하나로 판정해 "`# Abstract` 아래 `## Overview`" 하위 절을 통째로 놓쳤다. `is_references`와 대칭으로 `split_for_embedding()`이 헤더 계층 전체로 `is_abstract`를 계산해 조각에 실어 보내고 `extract_abstract()`는 플래그만 읽게 수정 — **같은 버그를 두 번 겪은 셈이라, 라벨(표시용)과 소속 판정을 같은 값에서 파생시키지 말라는 원칙을 모듈 docstring에 명문화**. **(2) abstract 문서 도입으로 백그라운드 요약 트리거가 새던 경로** — `retrieve()` 후보가 `doc_type == "fulltext_chunk"`뿐이라, `MAX_CHUNKS_PER_PAPER=2` 아래 그 논문 몫이 abstract 하나만 남으면(effort=low는 top_k=2라 현실적) 논문이 context에 들어왔는데도 생성이 시작 안 됐다. 후보를 `paper_id` 보유 문서 전체로 넓히되 **이번 검색에 summary 문서가 나온 논문은 제외**(요약 존재의 공짜 증거 — `_fetch_summary()` DB 조회를 아낌, `_PERMANENTLY_FAILED`를 DB 조회 앞에 둔 07-28 수정과 같은 논리). **(3) `get_paper_summary()`의 fulltext_chunk 중복 조회** — `_fetch_fulltext_chunks()`와 `_fetch_bib_meta()`가 같은 `where`로 각각 조회해 122청크면 전체를 두 번 끌어왔다(계측 확인, 4회→3회로 감소). 둘을 `_fetch_fulltext()`(조회 1회로 `(chunks, bib_meta)` 반환)로 합치고 화이트리스트 선별은 `_pick_bib_meta()` 순수 함수로 분리 |
| 07-31 | 08-07① 관심사 RDB 스키마+CRUD | 새 모듈 `interests.py` — `data/app.db`(체크포인트와 파일 분리, 디렉터리는 공유)에 `interests` 테이블(로드맵 필수 템플릿 필드: title/looking_for/already_known/excluded_topics + created_at/updated_at). ORM 없이 표준 라이브러리 `sqlite3`(테이블 하나짜리엔 SQLAlchemy가 과함 — 단순 경로부터, 조인·마이그레이션이 복잡해지면 재검토). `create_interest`/`list_interests`/`get_interest`/`update_interest`(부분 갱신, 화이트리스트 밖 필드는 `ValueError`) — `conn` 파라미터로 커넥션 주입 가능(`paper_ingest.py`의 `vectorstore=None` 패턴과 같은 결). **테스트는 가짜 객체 없이 `sqlite3.connect(":memory:")` 그대로 사용** — Chroma와 달리 sqlite3는 인메모리 연결이 진짜 DB라 목이 필요 없음(10개, 0.01초). 실제 `data/app.db` 생성·스키마·삽입까지 수동 스모크 테스트로 확인 |
| 07-31 | 08-07②③ 문서 작성기(관심사) + `interrupt` 메커니즘 확정 | **UX 재설계(설계 논의)**: 당초 "물리 QA가 직접 작성"에서 "물리 QA는 제안만, 작성·확인은 관심사 서비스"로 변경 — 핸드오프는 대화 내용을 복사하지 않고 `thread_id` 하나만 넘김(6-4로 이미 영속화된 `checkpoints.sqlite`를 관심사 서비스가 다시 읽음). **아키텍처 결정(`langgraph.types.interrupt` 실제 소스 확인)**: (1) `interrupt()`는 자신이 속한 그래프에 체크포인터가 있어야 하는데 물리 QA는 의도적으로 체크포인터 없는 fresh-invoke 자식 그래프라 그 패턴을 못 씀 → 문서 작성기는 물리 QA처럼 래퍼-자식으로 안 만들고 **완전히 독립된 그래프**(`interest_writer.py`)로 분리, orchestrator와 **같은 체크포인터 파일**(`data/checkpoints.sqlite`)을 `thread_id`만 다르게 써서 재사용(새 파일 안 만듦). (2) "재개 시 노드 전체가 처음부터 재실행"이 확인된 핵심 제약 — `interrupt()`를 부르는 `confirm` 노드는 LLM·DB 호출을 절대 안 하고 상태를 읽어 보여주기만 함, 초안 생성(`draft`)·중복 검사(`dup_check`)는 그 앞 노드에서 끝내 이미 체크포인트에 커밋해둠(재개돼도 안 다시 돎). **구현**: `InterestWriterState` + 노드 4개(`draft`→`dup_check`→`confirm`→조건부→`save`). `draft`는 `seed_thread_id` 있고 `title` 비어있을 때만(물리QA 핸드오프) `config["configurable"]["qa_checkpointer"]`로 주입받은 체크포인터로 `orchestrator.graph`를 다시 컴파일해 그 thread의 대화를 읽어 LLM 추출, 이미 채워져 있으면(수동 입력) LLM 호출 0. `dup_check`는 `interests.list_interests()` 전체를 프롬프트에 넣어 LLM 판정(관심사가 없으면 LLM 호출 0). `confirm`의 재개값은 `{"action": "create"/"update_existing"/"cancel", "edits": {...}}` — dict가 아니거나 action이 이상하면 안전하게 cancel. **테스트**: 노드별 순수 로직은 몽키패치로 검증, 그래프 전체는 `InMemorySaver`(async 메서드 완전 지원 — 동기 `SqliteSaver`와 달리 테스트에 그대로 씀)로 실제 실행해 (a) 1차 `ainvoke()`가 `__interrupt__`로 정지하는지 (b) `Command(resume=...)`로 재개했을 때 `dup_check`의 LLM 호출 횟수가 **여전히 1번**인지(재실행 안 됨의 실제 증거) (c) edits 반영 (d) cancel 시 미저장을 확인(17개). **실사용 검증**: 별도 프로세스 두 번(1차 정지 확인 → 2차 `Command(resume=...)`로 재개)을 실제 `AsyncSqliteSaver`로 실행 — `data/app.db`에 실제로 저장되는 것까지 확인(6-4와 같은 방식의 프로세스 간 검증) |

## 🔄 진행 중

| 날짜 | 항목 | 상태 |
|---|---|---|
| 07-15~ | 베이스라인 완주 | gemini 쿼터 리필 대기 — bare gemini, graph(gemini-only)에서 역전 재현 확인 후 전체 비교표 완성 |

## 📅 예정

| 목표 시기 | 항목 | 내용 |
|---|---|---|
| 08-07 | 관심사 서비스 (①) | 관심사 저장소(**RDB/SQLite** — 설계 노트 "VDB vs RDB" 참고, 중복 검사는 전체 목록 프롬프트 LLM 판정) + 문서 작성기 능력(대화 → 템플릿 문서, 유사도 중복 검사 → 기존 편집 제안, 등록 확인 `interrupt`) + 턴 종료 후 훅("대화 내용을 관심사로 등록할까요?" — 싼 모델 1회 판정). 작성기는 ⑤ 실험도구와 템플릿만 갈아끼워 공용. **템플릿에 "무엇을 찾고 있나 / 이미 아는 것 / 제외할 주제" 필드 필수** — ②b 관련도 판정 정확도가 여기에 달려 있다(평가 기준의 일부는 사용자가 써주는 것). **진행 상황(07-31)**: RDB 스키마+CRUD(`interests.py`)·문서 작성기 능력(`interest_writer.py`, `interrupt` 포함) 완료 — 아래 완료 표 참고. **UX는 애초 계획에서 수정됨**: 물리 QA가 직접 작성하지 않고 제안만 하고 `thread_id`를 관심사 서비스로 넘김(대화 복사 안 함). 남은 것: 턴 종료 후 훅(물리 QA 쪽, 싼 모델 1회 판정) → 호출 경로(API). **(좋은 모델로 검사 권장 — 첫 RDB 도입 + 첫 `interrupt` HITL이 겹친다. 재개 경로가 실제로 살아나는지, 중단된 등록이 반쯤 쓰인 채로 남지 않는지가 코드만 읽어선 잘 안 보인다)** |
| 08-09 | 추천 검색 (③) + 스크리닝 (②b) + 논문 카탈로그 | ②b: **abstract만** 보고 관련도 판정(유일한 LLM 판단) + 확인 가능한 축 **병기**(단일 점수로 합치지 않음): peer-review 여부(arXiv `journal_ref`), 연간 인용수, 출판 연도 — 전문을 읽지 않는다. 기각 이력(`dismissed`)을 기준 검증용 레이블로 축적. 논문 검색 어댑터(쿼리 → abstract+서지+지표 후보 목록)도 여기서 분리. ③: **관심사에서 트리거할 때만** 실행 (cron 아님) — 검색 → ②b 스크리닝 → 랭킹 → 카탈로그에 recommended 기록. 논문 카탈로그(SQLite, DOI 기본 키, `status: recommended/owned/dismissed`) — 등록 시 DOI 매칭으로 recommended → owned 전환(추천에서 내려감). 권위 논문 목록(인용수 기반)도 관심사별 조회·캐시. **검색·평가 내부를 공용 함수로 분리**해 참고문헌 추천기와 공유(추천기는 문맥 기반 온디맨드, QA 풀 호출은 라우터 분기). **(좋은 모델로 검사 권장 — 이 프로젝트에서 데이터 무결성 위험이 가장 큰 지점. `paper_id`가 기본 키인데 VDB·카탈로그 두 저장소에 나뉘어 있고, 상태 전이(recommended→owned)와 다대다 조인이 여기서 처음 생긴다. 07-28 `retrieve()` 2k 버그처럼 "저장소가 늘면 필터가 한 군데 빠진다"가 이 저장소의 반복 실패 패턴)** |
| 08-11 | 라이브러리 표면 1차 | 관리 UI 통합 화면(Streamlit multipage) — **논문 탭**(PDF·DOI·arxiv id 등록 → ② ingest, 카탈로그 상태 표시. 등록의 주 경로) + **관심사 탭**(카드별 보유/추천/권위 논문 목록, "지금 검색" 트리거). 실험도구 탭은 ⑤와 함께, 지식 노트 탭(`source_type: user_note` 신뢰도 구분)은 후속. **프론트 스택 재검토 겸행** — 표면 4개엔 Streamlit 한계, React 등 전환 검토. **(좋은 모델로 검사 권장 — UI 자체가 아니라 `register_paper()`를 "파싱·검증 → 확인 → 저장" 2단계로 쪼개는 부분. 지금은 한 함수가 원자적으로 처리하는 걸 쪼개는 거라 중간에 끊겼을 때 반쯤 저장된 상태가 남을 수 있다)** |
| 후순위 아이디어 | 피드 표면 + cron 수집 | 관심사와 무관하게 hype 소식 크롤링 → 키워드 태깅 → 관심사 일치 키워드 색 강조·상단 정렬. **설계 방향은 유효하지만 후순위로 내림(07-28)** — 혼자 쓰는 규모에 크롤링 인프라와 cron 스케줄러까지 얹는 건 과하고, 지금 우선순위(논문 파이프라인·관심사·추천)와 겹치는 부분도 없다. 착수한다면 **UI 작업으로 라이브러리 표면·프론트 스택 전환과 묶어서** 진행. `docs/architecture.png`는 아직 표면 4개(피드 포함)로 그려져 있음 — 다음 아키텍처 변경 때 함께 갱신 |
| 08-10 | 메인 챗 라우터 | QA / 문서 작성기 호출 / 추천 조회 3~4갈래 얇은 라우터 (거대 슈퍼바이저 아님). **후속 질문 재작성 통합** — 라우팅 결정과 "에이전트에 넘길 정제된 task"를 structured output 한 번에. 라우팅 정답 평가셋(10~20문항)도 함께 구축. **(좋은 모델로 검사 권장 — 능력이 둘 이상이 되는 첫 지점. `physics_qa_node`의 래퍼 계약(새 메시지만 슬라이싱, State 비공유)을 다른 능력에도 똑같이 지키는지, 능력마다 제각각 새지 않는지가 핵심)** |
| 08-12 | 장기기억 | VDB 메타데이터 필터링으로 user_id 태그 — 유저별 LTM 분리, 검증된 문헌의 LTM 승격. `disabled_models`도 부모 State 공유로 전환(쿼터 소진을 에이전트마다 재발견하지 않게). **(좋은 모델로 검사 권장 — 검사 목적이 다른 항목들과 다르다. 여긴 "동작하나"가 아니라 "user_id 필터가 모든 검색 경로에 빠짐없이 걸렸나"가 전부다. 한 경로만 빠져도 남의 데이터가 답변에 섞이는데 테스트로는 잘 안 드러난다 — `retrieve()`·참고문헌 추천기·②b·라이브러리 조회를 전부 훑어야 함)** |
| 08-13 | 메시지 트리밍 | 멀티턴에서 messages 무한 성장 → 긴 대화의 generate 비용 관리 (tokens_used로 성장 측정 가능). **(좋은 모델로 검사 권장 — `final_answer`의 `turn_start_len` 슬라이싱·`RemoveMessage` 정리와 정면으로 맞물린다. 트리밍이 턴 경계를 어긋나게 만들면 대화 이력이 조용히 깨지고, 그 증상이 몇 턴 뒤에야 나타난다)** |
| 8월 중 | verify 구성 비교 실험 확장 | self / 교차 / 무 verify / 다중 모델 앙상블 — correctness·토큰·지연 지표로 체계화 (현재 부분 진행: Qwen self-verify vs claude-verify 완료). **bare vs graph 0.915 vs 0.926 차이의 반복 실행 신뢰도 검증(3회 이상 평균)**도 함께 진행 |
| 8월 하순 | 실험도구 DB (⑤) + 연구 워크플로우 (⑥) | 장비 spec을 **RDB(SQLite) 구조화 레코드로 — 임베딩하지 않는다**(실험 설계의 질의가 "측정 범위 X 이상" 같은 범위 조건이라 VDB로는 불가). 문서 작성기 재사용. 가설 수립 → 실험 설계(Plan-and-Execute) → 실험 운영을 별도 표면(단계형 화면)으로. 안전 가드레일 `interrupt_before` HITL — 재실험 루프는 실험 설계만 재호출. **각 단계가 참고문헌 추천기를 호출해 워크플로우 공유 references 목록에 누적**(서지 + 인용 이유 + 추가 단계) — 가설(배경)·설계(방법론)·운영(결과 비교). **(좋은 모델로 검사 권장 — 안전 가드레일 `interrupt_before`가 실제로 "사람 승인 전까지 진행 불가"를 보장하는지. 우회 경로가 하나라도 있으면 가드레일이 있는 척만 하는 게 되고, 며칠씩 걸리는 상태 있는 워크플로우라 재시작·재실험 루프에서 상태가 어긋나기 쉽다)** |
| 8월 하순 | 논문 작성 능력 (⑦) | 실험 결과·사용자 문서 기반 초안 → ②로 자체 검토 → 재작성 (Evaluator-Optimizer, 검증된 패턴 재사용) + 번역 레이어(후처리 노드). **워크플로우가 누적한 references 목록을 소비**해 인라인 인용·참고문헌 생성 — 목록에 없는 인용은 환각 신호로 자체 검토에서 반려. **(좋은 모델로 검사 권장 — "목록에 없는 인용은 반려"가 실제로 빠짐없이 걸리는지. 여기가 뚫리면 그럴듯한 가짜 인용이 최종 산출물에 남는데, 이 프로젝트에서 가장 비용이 큰 실패다)** |
| 최종 다듬기 | 스트리밍 중 인터럽트 — 취소·대기열 | 스트리밍으로 답하는 도중 들어온 입력 처리. ① **취소(ESC)**: 클라이언트 중단을 서버가 감지해 `astream` 루프를 끊음 — 이때 `final_answer`가 실행되지 않아 **이번 턴의 재시도 초안·tool 메시지가 정리되지 않고 checkpointer에 남는 문제**가 생김(다음 턴 대화 이력 오염) → 중단 시 턴 롤백 또는 aborted 표시가 필요. 소모한 토큰은 정산해 표시. ② **대기열**: 같은 `thread_id`에 동시 invoke가 들어가면 checkpointer 상태가 깨지므로 **thread별 직렬화는 UX가 아니라 정확성 요구사항** — 처리 중 도착한 프롬프트는 큐에 넣고 턴 종료 후 처리(거절·현재 턴 중단 대신 큐 선택). ③ ESC 키 바인딩은 Streamlit로는 어려움 — 프론트 스택 전환과 함께 진행. **(좋은 모델로 검사 권장 — 항목 설명 자체가 이미 checkpointer 정합성 위험을 지목하고 있다. 6-4로 체크포인트가 디스크에 영속화된 뒤로는 깨진 상태가 재시작해도 안 사라지고 계속 남는다는 점이 더해졌다)** |
| 실제로 걸릴 때 | 요약 재귀 분할 (6-3 보류분) | 예산 초과 논문을 만나면 착수 — 청크를 나눠 각각 추출한 뒤 합친다. **현 결정은 전부 코드 병합 유지**, 착수 시 `core_claims`만 LLM 선별로 전환하는 안을 기본 후보로 검토(근거·조건은 아래 설계 노트 "reduce 정책" 참고). 현재는 `get_paper_summary()`가 한 번에 호출하고 초과 시 `ContextBudgetExceeded`로 정직하게 실패. **(좋은 모델로 검사 권장 — reduce에서 사실이 조용히 망가지는지. 틀린 요약이 "맞는 것처럼" 캐시에 저장되면 하류(④ QA·⑦ 인용)가 그대로 믿는데, 출력만 봐선 뭐가 유실됐는지 알 수 없다)** |
| 이후 | 요약 표시 형식 — 산문 렌더링 | `_render_summary_text()`가 지금은 구조화 필드를 불릿 목록으로 렌더링하는데, 사용자가 읽기엔 한 문단 산문이 자연스럽다. **저장(구조화 `extraction_json`)과 표시(산문)를 분리하면 병합 정책과 무관하게 바꿀 수 있다** — 구조화 레코드는 ⑦ 인용 검증·재현성용으로 그대로 두고 산문은 파생 뷰. 템플릿으로 먼저 시도하고 어색하면 표시 전용 LLM 패스를 검토(실패해도 원본 구조는 안 깨짐). RAG 임베딩 텍스트로도 산문이 자연어 질문과 더 잘 매칭될 가능성 |
| 실제로 걸릴 때 | 헤더 탐지 폴백 2단 (6-3 보류분) | `pymupdf4llm` 헤딩은 폰트 크기 휴리스틱이라 `**1. Introduction**`(볼드 문단)으로 나오거나 아예 안 잡히는 논문이 있다. 섹션이 1개거나 임계 크기를 넘으면 → 섹션명 정규식(`Abstract\|Introduction\|Method\|Result\|Discussion\|Conclusion\|Reference\|Bibliography`, 대소문자 무시) → 그래도 실패면 문단 분할. 실제로 그런 논문을 아직 못 만나 미착수("단순 경로부터") |
| 이후 | 자체 서빙 엔진 만들기 | GGUF 추론을 llama-server에 맡기지 않고 직접 구현(토크나이징·배칭·KV 캐시 등), 원본(llama-server 서빙) 대비 정확도·속도를 evaluate로 비교. 에이전트 서빙(운영) 학습이 목적 |
| 이후 | 자잘한 정리 | `ingest.py`의 안 쓰는 import 제거(죽은 `HuggingFaceEmbeddings`, 미사용 `os`/`hashlib`) · `verify()`의 "차순위도 실패→검증 생략" 분기에서 `disabled_models`가 리셋되는 버그(`state.disabled_models` → `+ [state.generated_by]`, 현재는 이 분기가 바로 종료로 이어져 영향 거의 없음) · `graph.py` `MAX_CHUNKS_PER_PAPER` 주석이 중복 원인을 3가지로 열거하는데 abstract가 늘어 이제 4가지(주석 낡음) · `os.makedirs(os.path.dirname(CHECKPOINT_DB_PATH))`가 `main.py`·`orchestrator.py` 두 곳 중복이고 경로를 파일명만으로 바꾸면 `dirname`이 `""`이라 터짐 · `register_paper()`의 `{**fetched, **(bibliographic or {})}`는 호출자가 `{"title": None}`을 명시하면 arxiv 제목을 `None`이 덮어씀 |
| 이후 | 논문 품질 평가 재검토 | 과학적 타당성·신규성 판정은 현재 보류(설계 노트 참고). **⑦ 논문 작성이 실제로 소비할 수 있게 된 시점에** 기준을 다시 설계 — 소비처가 없으면 기준을 검증할 방법도 없음. 검증 레이블은 카탈로그 `dismissed` 이력으로 확보 |
| 이후 | arXiv LaTeX 소스 경로 | arXiv는 PDF 외에 e-print 소스(대개 원본 .tex)도 제공 — .tex을 파싱하면 수식·섹션 구조·참고문헌 항목이 온전해서 PDF 추출보다 품질이 훨씬 높다. 최종 형태는 **"업로드 PDF는 PyMuPDF / arXiv 논문은 LaTeX 소스" 이중 경로**. 6-3에서는 범위 밖(PDF 경로 하나로 먼저 완성) |
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

**논문 처리 3분할 (07-28)** — 6-3 착수 전 재검토 결과:

- 요약기(②a): 입력은 **보유 논문 전문**, 호출자는 라이브러리·QA·⑦. 비싸고 드묾 → lazy 생성 + 캐시. 등록 시점에 하는 건 인코딩(청킹·임베딩)뿐이고 요약은 필요할 때
- 스크리닝(②b): 입력은 **abstract + 지표**, 호출자는 ③·참고문헌 추천기. 싸고 대량 → 전문을 읽지 않음(유료 저널은 읽을 수도 없음). LLM은 관련도만, 권위·신뢰도는 저널·인용수 계산 (LLM에 권위를 물으면 환각)
- 검색 어댑터: 쿼리 → abstract+서지+지표 후보 목록. 지금은 arxiv·웹, 나중에 Crossref/OpenAlex로 교체 — **지표 필드는 스키마에 미리 두고 비워둔다**(API 붙일 때 채우면 코드 변경 없음)
- 열린 질문: 전문 청크와 요약을 한 컬렉션에 `doc_type`으로 둘지 별도 컬렉션으로 둘지 — 지금은 한 컬렉션+필터로 시작하되 검색 품질 보고 재검토

**논문 평가 기준 — "평가" 분해와 품질 판정 보류 (07-28)**:

- "논문 평가"를 하나의 기능으로 상정한 게 문제였음. ②a와 ②b가 답할 질문이 다름 — ②b는 "읽을 가치가 있나"(선별·우선순위), ②a는 "무엇을 주장하고 어디까지 믿을 수 있나"(인용 시 주의사항)
- **과학적 타당성은 판정하지 않는다**: 실험 설계 건전성·통계·신규성은 피어 리뷰 영역. LLM에 신뢰도 점수를 물으면 그럴듯한 노이즈가 나오고, ⑦·가설 수립이 그걸 신호로 취급하므로 없는 것보다 나쁨. **07-15 verify 판정 기준 수정과 같은 실패 양상**(모호한 품질 판정 요구 → "정확하다면서 반려"로 3라운드 낭비)
- ②a는 판정 대신 **구조화 추출**: 핵심 주장 1~3개 / 근거의 종류(실험·이론·시뮬레이션, 조건·규모) / **저자가 스스로 밝힌 한계**(limitations 섹션 — 저자 진술 인용은 판단이 아니라 추출이라 신뢰 가능) / 저자가 언급한 미해결 지점(eval.json의 unsolved 카테고리와 같은 결) / 확인 가능한 사실(preprint 여부, 코드·데이터 공개 언급)
- ②b는 축을 **합치지 않고 병기**: 관련도(유일한 LLM 판단) / peer-review 여부(**arXiv API `journal_ref` 필드 — 지금 당장 구현 가능한 강한 신호**) / 연간 인용수(총 인용수는 오래된 논문에 유리하므로 정규화) / 출판 연도(최신이 항상 좋은 게 아님 — 기초 물리는 정전, 실험 기법은 최신). 저자 h-index 등 명성 지표는 제외(편향)
- **품질 평가 자체는 보류 → ⑦ 논문 작성이 실제로 소비할 수 있게 된 시점에 재검토.** 평가가 값어치 있었던 이유가 ⑦의 활용인데, 소비처가 없으면 기준을 검증할 방법도 없음
- 검증 수단은 이미 확보: 카탈로그 `status: dismissed`가 사용자 판단 기록 = 공짜 정답 레이블. 기준 변경 시 "예전 기각 논문을 여전히 상위에 올리나"로 비교
- 선행 요구: ① 관심사 템플릿에 "무엇을 찾고 있나 / 이미 아는 것 / 제외할 주제" 필드 — 관련도 판정 정확도가 여기에 달려 있음

**전문 처리 — 헤더 기반 분할 + 점진적 길이 관리 (07-28)**:

- `pymupdf4llm`이 마크다운으로 뽑아주므로 `MarkdownHeaderTextSplitter`(LangChain)로 헤더(`#`/`##`) 기준 섹션 분할 — Abstract/Introduction/Methods/Results/Discussion·Conclusion/References로 나뉨. References 섹션은 여기서 태깅·제외
- **References 판정은 대표 라벨이 아니라 헤더 계층 전체로** (07-28, 코드 리딩 질문에서 발견): 각 조각은 `MarkdownHeaderTextSplitter`가 붙인 헤더 메타데이터(h1/h2/h3 등, 값은 헤더 텍스트) 중 가장 깊은 것 하나를 대표 라벨로 표시하는데, `is_references` 분류까지 이 대표 라벨 하나로 판정하면 "# References" 아래 "## Appendix A" 같은 하위헤더가 있는 조각은 라벨이 "Appendix A"라 정규식이 안 걸려 References가 아닌 것으로 잘못 분류돼 버린다. 대표 라벨(표시용, 깊은 헤더 하나)과 `is_references`(분류용, 헤더 계층 전체에 `any()`로 판정)는 요구가 다르므로 값을 분리해서 계산
- **구조화 추출**(핵심 주장·한계·미해결 지점)은 관련 섹션(초록·서론·결론 등)을 묶어 LLM에 전달 — 길이가 컨텍스트를 넘으면 더 작은 단위(`##` 서브헤더 → 문단)로 재귀적으로 쪼개 각각 요약한 뒤 합치는 점진적 분할(map-reduce와 같은 원리)로 대응
- **임베딩 청크**(`fulltext_chunk`)는 검색 정밀도가 목적이라 헤더 섹션 경계와 무관하게 기존 `ingest.py` 방식(500자/오버랩 50)대로 잘게 유지 — 섹션 정보는 메타데이터로만 기록(예: `section: "results"`), 청크 크기 자체를 섹션 경계에 맞추지 않음
- **모델 호출은 `invoke_with_fallback` 그대로 재사용, 별도 모델 호출 경로를 새로 만들지 않음**: 길이를 호출 **전에** 먼저 체크해서 넘으면 미리 쪼개므로, "컨텍스트 초과로 `BadRequestError`가 나서 엉뚱하게 다음 모델로 fallback되는"(진짜 원인은 길이인데 모델 탓으로 처리되는) 상황 자체가 애초에 안 생김 — `models.py`를 "model_map+fallback 정책의 단일 지점"으로 유지한다는 07-13 원칙과 일치
- **reduce는 자유 요약이 아니라 스키마 병합**: map-reduce에서 사실이 망가지는 곳은 언제나 merge 단계 — 부분 요약을 다시 LLM에 넣어 "합쳐서 요약"하면 구조화 필드(주장·한계·미해결)가 뭉개진다. 각 map 호출이 **같은 Pydantic 스키마**로 반환하게 하고 reduce는 **리스트 병합 + 중복 제거를 파이썬 코드로** 수행(재현성 확보, 토큰 0). LLM은 목록이 과도하게 길 때 중복 정리·우선순위에만 호출. `verified`·`final_answer_structure`로 이미 쓰는 구조화 출력 패턴의 연장
- 추출 항목마다 **`from_section` 필드**를 남긴다(어느 섹션에서 나온 주장인지) — ⑦의 인용 검증에서 근거 위치를 되짚는 데 쓰이고, 지금 넣는 비용은 거의 없음
- **컨텍스트 예산은 모델별로 `models.py`에 선언**: gemini-2.5-flash(~1M)·claude-haiku(200k)에서는 물리 논문 전문(대략 1~2만 토큰)에 초록·서론·결론만 골라 보내면 **분할 경로가 사실상 발동하지 않는다**. 반면 `Qwen-tuned`는 로컬 llama-server의 `n_ctx`가 작으면(4096 등) 바로 걸린다 — 즉 "넘칠 것 같으면"의 기준이 모델마다 다르므로 예산을 `model_map` 옆에 두고 요약기는 조회만 한다(모델 정책 단일 지점 원칙)
- **그래서 구현 순서는 단순 경로 우선**: 한 번에 넣는 경로 + 예산 초과 가드부터 만들고, 재귀 분할은 실제로 걸리는 것을 확인한 뒤 채운다(거의 실행되지 않는 기계를 먼저 만드는 낭비 방지). 초과 시 **조용히 잘라내지 말고 정직하게 실패** — 잘라서 요약하면 "저자가 밝힌 한계"가 잘린 쪽에 있었는지 알 수 없게 되어 틀린 요약을 맞는 것처럼 저장하게 된다. `comment`에 "논문이 길어 요약 생성 불가(분할 처리 미구현)"로 고지
- **헤더 탐지 실패 폴백 2단**: `pymupdf4llm`의 헤딩 판정은 폰트 크기 휴리스틱이라 실제 논문에서 `## 1. Introduction`이 아니라 `**1. Introduction**`(볼드 문단)으로 나오거나 헤딩이 전혀 안 잡히는 경우가 있고, 그러면 `MarkdownHeaderTextSplitter`가 거대한 섹션 하나를 돌려줘 이후 로직이 헛돈다. 섹션이 1개거나 임계 크기를 넘으면 → 섹션명 정규식(`Abstract|Introduction|Method|Result|Discussion|Conclusion|Reference|Bibliography`, 대소문자 무시)으로 재시도 → 그것도 실패하면 문단 분할. References는 `Bibliography` 표기도 함께 잡는다
- **논문 id 정규화 + 재등록 처리**: 카탈로그 기본 키는 DOI로 잡았지만 **arXiv preprint는 DOI가 없고 업로드 PDF는 둘 다 없을 수 있다** → `paper_id`를 규칙으로 정하고 DOI는 별도 컬럼(nullable·unique)으로 분리. ① DOI 있으면 `doi:10.xxxx/...` ② 없고 arXiv면 `arxiv:2401.12345` ③ 둘 다 없으면 파일 내용 해시(`ingest.py`에 import된 채 미사용인 `hashlib`이 여기서 쓰인다). preprint가 나중에 게재돼 DOI가 생겨도 `paper_id`는 불변, DOI 컬럼만 채우면 됨(추천→보유 매칭은 DOI·arXiv id 양쪽으로). 청크 id는 `{paper_id}-{i}`이며, **재등록 시 청크 수가 줄면 이전 잔여 청크가 남으므로** `where={"paper_id": ...}`로 삭제 후 재삽입

**VDB vs RDB — 관심사·실험도구는 RDB로 (07-28 결정)**:

- **갈림선은 "RAG 검색 대상인가"**: 논문(전문 청크·요약)과 지식 노트는 QA가 의미 검색으로 찾아야 하므로 VDB. 관심사·실험도구·논문 카탈로그는 사람이 관리하고 시스템은 id·조건으로 조회하므로 RDB(SQLite).
- **관심사(①)를 VDB → RDB로 변경한 이유** (당초 "VDB 컬렉션 — 유사도 검색으로 중복 검사"에서 수정):
  - *편집이 일급 연산이다* — 문서 작성기가 "중복이면 기존 편집 제안"을 하도록 설계됐는데, VDB에서는 한 필드만 고쳐도 문서 전체를 재구성·재임베딩해야 한다. 템플릿 필드(찾는 것/아는 것/제외 주제)가 있으니 필드 단위 수정이 흔하다.
  - *관심사↔논문이 다대다다* — 라이브러리 관심사 탭의 "카드별 보유·추천·권위 논문 목록"은 조인이다. 카탈로그가 이미 SQLite인데 관심사만 Chroma에 있으면 두 저장소를 오가는 수동 동기화가 되고(추천이 `dismissed`로 바뀔 때마다 양쪽 갱신), 같은 DB에 `interest_paper` 조인 테이블(`status`·`score`·`screened_at`)을 두면 쿼리 하나로 끝난다.
  - *규모가 작다* — VDB를 고른 유일한 이유가 중복 검사였는데, 수십 개면 **전체 목록을 프롬프트에 넣고 LLM에게 묻는 편이 더 정확하다**(관심사 중복은 표현이 달라도 의미가 같은 경우가 많아 코사인 유사도가 잘 못 잡는다). 수백 개가 되면 그때 인덱스를 얹는다 — "단순 경로부터".
- **실험도구(⑤)는 RDB, 임베딩하지 않는다** ("+ 선택적 임베딩" 문구 삭제): 실험 설계가 던질 질문이 "측정 범위가 X 이상인 장비 있나?" 같은 **범위 조건 조회**라 VDB가 원리적으로 못 한다. 자연어 탐색이 필요하면 목록이 짧으니 프롬프트에 넣으면 된다.
- **파일 배치**: 6-4에서 `SqliteSaver`가 들어오면서 SQLite가 이미 스택에 있다(표준 라이브러리라 새 의존성도 없음). 단 **체크포인트 DB와 앱 데이터 DB는 파일을 분리**한다(전자는 LangGraph가 스키마를 관리, 후자는 우리 것). 둘 다 `chroma_db`처럼 바인드 마운트되는 디렉터리(예: `data/`)에 둬야 컨테이너 재시작에 살아남는다 — `docker-compose.yml`·`.gitignore`·`.dockerignore` 반영 필요.

**abstract와 ②a의 관계 (07-28)** — "abstract만 있으면 요약기가 필요 없지 않나?"에 대한 답:

- **abstract는 `PaperExtraction` 다섯 필드 중 `core_claims` 하나만 커버한다.** `author_stated_limitations`는 Discussion·Limitations 절에, `unresolved_questions`는 Conclusion·Future Work에, `code_data_availability`는 Data Availability 문단·각주에, `evidence`의 조건·규모(표본 크기·파라미터)는 Methods에 있다 — 넷 다 구조적으로 본문에만 있다.
- 이건 우연이 아니라 초록의 장르적 성격이다: **초록은 읽게 만들려고 쓰는 글이라 주장은 강하게 쓰고 유보는 본문에 둔다.** abstract만으로 요약하면 저자의 헤지를 통째로 잃는데, 그건 "저자가 스스로 밝힌 한계를 추출한다"는 이 프로젝트의 핵심 가치와 정반대다. → **②a는 abstract의 대체가 아니라 보완이다.** 스키마·파이프라인 재편 불필요.
- 다만 **지금 abstract를 그냥 버리고 있다**: `arxiv_search()`가 주는데 `_BIBLIOGRAPHIC_WHITELIST`에서 빠져 저장되지 않는다. 화이트리스트의 원래 의도는 "청크 122개에 1~2천 자를 복제하지 말자"였지 "버리자"가 아니었다 → **한 번만 저장**하면 해결.
- abstract를 저장할 값어치: 요약이 lazy 생성이라 **등록 직후~요약 생성 전까지 보여줄 게 없는 공백**이 있는데, 저자가 쓴 abstract가 그 구간을 공짜로 메운다(라이브러리 목록·RAG 검색 양쪽). 요약 생성이 실패한 논문(`_PERMANENTLY_FAILED`)에도 최소한의 표시가 남는다.
- **검증은 "주장 대조"가 아니라 "제목 일치"로**: abstract와 추출된 `core_claims`를 대조해 검증하자는 발상은 불일치 원인이 (a) 추출 오류 (b) 초록이 본문과 다른 걸 강조 (c) PDF가 v1이고 arxiv 기록은 v3 — 셋 다 흔해서 신호의 정밀도가 낮고, 비교하려면 LLM을 또 불러야 한다. 반면 제목 문자열 비교는 결정론적·고정밀이고 실제 사고(id 오입력·다른 논문 업로드)를 잡는다.

**abstract·summary 저장 위치 — RDB·VDB 이중 저장 (07-30, 논의 중 정정)**:

- "abstract도 summary도 둘 다 VDB에 넣어야 하나, RDB(카탈로그)면 안 되나?"에 대한 답은 "abstract는 RDB만"이 아니다 — **summary와 같은 이중 저장**이 맞다. 처음엔 abstract의 용도를 단일 저장·추출 프롬프트 앵커·제목 검증(전부 `paper_id` 정확 키 조회)뿐이라고 봤는데, 위 "abstract와 ②a의 관계" 절(139번째 줄)이 이미 적어둔 "라이브러리 목록·**RAG 검색** 양쪽"을 놓치고 있었다.
- **abstract가 의미 검색에도 필요한 이유**: summary는 lazy 생성이라 등록 직후엔 없는 경우가 흔하다. 그 공백 동안 QA가 참고할 게 fulltext_chunk(500자 조각)뿐인데, 저자가 쓴 abstract는 (1) 그 공백을 메우고 (2) 우리가 LLM으로 뽑은 summary보다 원문 그대로라 신뢰도가 높다. 그러니 abstract도 QA의 `similarity_search_with_score`에 걸리도록 **VDB에 임베딩된 채로 있어야** 한다.
- **VDB 저장 방식은 summary와 동일한 패턴** — `doc_type="abstract"`로 **논문당 문서 1개**(`ids=[f"{paper_id}-abstract"]`)만 만든다. `_store_summary()`(paper_ingest.py 280~293줄)가 이미 이 패턴이다: 별도 문서 하나에 텍스트(임베딩용)와 메타데이터를 같이 넣는 방식. **청크 메타데이터에 끼워 넣는 것과는 다르다** — 07-28에 겪은 복제 문제(`_BIBLIOGRAPHIC_WHITELIST` 도입 이유)는 서지정보를 `fulltext_chunk` 청크마다(`**bib_meta`로 병합) 반복해서 넣는 방식 때문이었지, "VDB에 문서를 만드는 것" 자체의 문제가 아니었다. `_store_summary()`처럼 논문당 1개 문서로 만들면 청크 수와 무관하게 복제가 없다.
- **RDB(논문 카탈로그, 6-6)에도 남긴다** — 프롬프트 앵커·제목 검증·목록 표시는 여전히 `paper_id` 정확 키 조회라 카탈로그가 더 잘 맞는다(임베딩 모델 로딩 없이 바로 조회).
- 결론: abstract는 RDB(정확 키 조회용)와 VDB(`doc_type="abstract"` 단일 문서, 의미 검색용) **둘 다에** 저장. summary도 이미 같은 이중 성격(구조화 데이터는 메타데이터로, 텍스트는 임베딩으로)이라 새로운 패턴이 아니다.
- 남은 문제: `_fetch_summary()`의 캐시 확인은 벡터 연산이 전혀 없는 순수 메타데이터 필터(`vectorstore.get(where=...)`)인데도 Chroma 객체를 만들어야 해서 bge-m3가 로드된다(read 커맨드 실행해도 로딩바가 뜨는 이유). 이 접근 패턴만 보면 RDB가 더 잘 맞지만, 캐시 확인이 핫 패스가 아니라서 지금 당장 이걸 이유로 이중 저장(요약 완료 여부 플래그를 카탈로그에도 두기)까지 할 값어치가 있는지는 미정 — 6-6 카탈로그 스키마 설계 시 재검토.

**6-3b① 실제 구현 + 답변 근거 표시 (07-29)** — 위 두 절의 결정대로 VDB 쪽(`doc_type="abstract"` 단일 문서)을 구현. RDB(카탈로그) 저장은 6-6 몫으로 아직 안 함. 구현 중 파생된 결정 세 가지:

- **답변 근거는 LLM이 아니라 결정론적으로 표시한다**: `graph.py`의 `describe_context_sources()`가 `state.context`의 메타데이터(paper_id/doc_type/title, source)만 보고 파인만·논문(제목+전문발췌/요약/초록)·웹검색 목록을 만들어 `final_answer()`의 `comment`에 붙인다. `verified`나 `final_answer_structure`에 필드로 넣지 않은 이유: "결정론적으로 계산 가능한 값은 LLM 스키마에 넣지 않는다"(§3 설계 원칙)와 같은 논리 — 이미 아는 사실(어떤 문서가 context에 들어왔는지)을 LLM에 다시 판단시키면 비용과 환각 위험만 생긴다. 대신 "실제로 답변이 그 문서를 썼는지"는 일부러 안 보여준다 — `generate()`가 "문서가 무관하면 무시해라"를 허용하므로 그건 비결정론적 판단이 필요해 이 함수의 책임 밖으로 뒀다(②a·②b의 "판정 아니라 추출" 원칙과 같은 결).
- **summary 문서도 title 등을 받는다**: `_fetch_bib_meta()`를 신설해 이미 `fulltext_chunk`에 복제돼 있던 서지 필드(`_BIBLIOGRAPHIC_WHITELIST`)를 꺼내 `_store_summary()`에 같이 넣는다 — `get_paper_summary()`가 `bibliographic`을 안 받는 별도 호출이라 처음엔 "더 큰 리팩터가 필요하다"고 잘못 판단했었는데, 실제로는 그 데이터가 이미 Chroma에 있어서(청크마다 복제돼 있음) 그냥 읽어와 재사용하는 정도로 충분했다.
- **arxiv_id만 있고 bibliographic이 없으면 자동으로 채운다**: `arxiv_api.py`에 `fetch_by_id()`(id_list 조회)를 신설 — `arxiv_search()`(키워드 검색)로 제목 등을 다시 찾으면 다른 논문이 걸릴 위험이 있으므로, 이미 아는 `arxiv_id`는 정확히 그 id로만 조회한다. `register_paper()`가 abstract가 없을 때만 호출(호출자가 이미 서지정보를 줬으면 조회 안 함), 호출자 명시값이 항상 우선, 조회 실패는 등록을 막지 않는다. 이로써 `register_paper()`가 "LLM 호출은 없다"에서 "네트워크 호출은 있을 수 있다"로 성격이 살짝 바뀌었다(스로틀 3초 있음, `arxiv_api.py`).
- **남은 한계**: `bibliographic` 없이(그리고 `arxiv_id`도 없이) 등록된 논문(해시 기반 `paper_id`)은 위 자동 조회 대상도 아니라서 여전히 title이 없다 — 데이터 자체가 없는 경우라 지금 범위에서 해결할 방법이 없다(근거 표시는 이 경우 `paper_id`로 폴백).

**제목 검증 — 막지 말고 경고, 단 등급을 나눈다 (07-28)**:

- **막지 않는다**: 불일치해도 등록 자체를 거부하지 않고 프론트에서 제목 칸·arxiv id 칸에 빨간 경고와 안내문을 띄워 사용자가 고치게 한다("조용히 자르지 말고 정직하게 실패"의 같은 결 — 시스템이 판정해서 차단하는 대신 사실을 알리고 사람이 결정).
- **경고 등급을 둘로 나눈다** (한 종류로 뭉뚱그리면 안 되는 이유): 제목 불일치는 성격이 다른 두 사고를 가리킨다.
  - *표기 차이* (줄바꿈·부제·LaTeX 기호·대소문자): 무해. 제목 후보 중 하나를 고르면 끝.
  - *아예 다른 논문* (arxiv id 오입력, 다른 PDF 업로드): 진짜 문제는 제목이 아니라 **`paper_id`**다. 제목만 고쳐 넘어가면 "id는 `arxiv:X`인데 내용은 Y논문"인 레코드가 카탈로그에 남고, `paper_id`가 기본 키라 나중에 "등록하면 추천에서 내려감" 매칭이 조용히 틀린다. → 이 등급에서는 제목 선택이 아니라 **"arxiv id가 맞습니까?"를 먼저 묻는다.**
- **최종 제목은 사용자가 고른다**: 후보는 ① PDF 첫 페이지에서 뽑은 제목 ② arxiv가 준 제목 ③ 파일명 ④ 직접 입력(텍스트박스). 선택 결과는 `register_paper(bibliographic={"title": ...})`로 넘기면 되므로 시그니처 변경이 필요 없다.
- **파일명은 검사 대상이 아니라 후보로만** (당초 안에서 수정): `2401.12345v2.pdf`·`paper(3).pdf`·`download.pdf`가 제목을 담은 파일명보다 훨씬 흔해 **불일치가 정상인 경우가 다수**다. 여기에 경고를 띄우면 거짓 경보가 쌓여 사용자가 경고 자체를 무시하게 된다. 대조 검사는 `arxiv 제목 ↔ PDF 추출 제목` 하나만.
- **"PDF 제목 추출 실패"는 불일치가 아니다**: 헤딩 인식이 폰트 크기 휴리스틱이라 제목이 안 잡힐 수 있다. 이때는 검사를 건너뛰고 경고 없이 arxiv 제목을 기본값으로 — 없는 것을 불일치로 처리하면 또 거짓 경보다.
- **검사 시점은 저장 전**: 지금 `register_paper()`는 파싱·식별·저장을 한 번에 하는데, 그 안에서 검사하면 이미 저장된 뒤라 고칠 수 없다. 라이브러리 UI(6-8)를 만들 때 "파싱·검증 결과 반환" / "저장" 두 단계로 분리한다(PDF를 두 번 파싱하지 않도록 파싱 결과를 넘기는 형태로).
- **실제 구현은 판정까지만, UI 연결은 미룸 (07-29)**: 위 설계대로 판정 로직(`paper/title_check.py`의 `classify_title_match()`)과 `register_paper()` 연결까지는 끝냈다 — 하지만 "저장 전 검사"·"2단계 흐름"·"사용자가 후보 중 고름"은 전부 라이브러리 UI(6-8)가 있어야 의미가 있어서 아직이다. 지금 `register_paper()`는 여전히 파싱→저장을 한 번에 하고, 판정만 반환값(`title_check`)에 얹어 등록 자체는 절대 막지 않는다. UI가 생기면 그 반환값을 그대로 소비(경고 등급별 다른 안내)하면 되고, "저장 전 검사"로의 전환(2단계 분리)은 그때 별도로 한다.

**요약 재귀 분할의 reduce 정책 (07-28 논의, 결론: 현행 유지 후 재검토)**:

착수 시점이 오면 다시 볼 것. 논의된 선택지는 (a) 전부 코드 병합 (b) `core_claims`만 LLM이 후보 중 선별·병합 (c) 부분 요약을 LLM에 다시 넣어 전체 요약 재작성.

- **(c)를 배제한 이유**: "1차에서 이미 LLM 불안정성을 감수했으니 2차도 같다"는 논리는 성립하지 않는다. 두 호출은 오류 성격이 다르다 — 1차는 입력이 원문이라 출력의 근거를 원문과 대조해 검증할 수 있고 오류가 그 조각에 국소화되지만, 2차는 입력이 이미 압축된 텍스트라 원문 대조가 불가능하고 **1차가 버린 건 복원할 수 없으며 1차가 비튼 건 증폭된다**(압축의 압축은 손실이 곱해진다). 같은 위험의 반복이 아니라 새로운 종류의 위험 추가다.
- **(b)의 근거 — 필드별로 경계 분절 위험이 다르다**: 청크 경계에서 잘린 주장을 코드 병합은 못 잇고 LLM은 이을 수 있다(LLM reduce의 유일한 실질 능력 차이). 그런데 `author_stated_limitations`는 보통 Limitations 섹션 한 곳에 열거되고 `code_data_availability`는 한 문장이며 `unresolved_questions`도 Discussion에 모여 있어 **항목이 원자적이라 잘릴 일이 적다**. 반면 `core_claims`는 논문 전체에 흩어져 조각마다 부분적으로 잡힌다. 필드별 비대칭 처리는 자의적인 게 아니라 이 분포 차이를 반영한다.
- **(b)를 지금 도입하지 않는 이유**: 경계 분절은 `split_into_sections()`의 `overlap_chars=300`과 헤더 기준 분할(경계가 임의 문자 위치가 아니라 섹션 사이)로 이미 상당히 완화돼 있고, 애초에 이 경로는 예산 초과일 때만 돈다 — gemini(80만 자)로는 논문 한 편에 사실상 안 걸리므로 실질적으로 `Qwen-tuned` 전용 문제다. **실제 출력을 보고 결정하는 게 맞다**(`Qwen-tuned` 예산으로 강제로 걸어보면 확인 가능). "단순 경로부터" 원칙 적용.
- **(b)로 갈 때의 제약**: LLM 호출을 "고르고 잇기"로 제한한다 — 프롬프트에 "후보들은 같은 논문의 서로 다른 부분에서 추출된 것이다. 중복을 합치고 조각난 주장을 잇되 **후보에 없는 내용을 새로 만들지 마라**"를 명시하고, 출력 스키마도 자유 텍스트가 아니라 `list[str]`로 유지. **병합 전 후보 목록을 메타데이터에 함께 남겨** LLM이 무엇을 버렸는지 사후에 볼 수 있게 한다(감사 가능성, 비용은 문자열 하나).
- **표시 형식은 이 결정과 무관**: "사용자에겐 불릿 목록보다 한 문단이 자연스럽다"는 별개 문제로, 저장(구조화)과 표시(산문)를 분리하면 병합 정책을 건드리지 않고 해결된다(위 예정 "요약 표시 형식" 참고).

**PDF 파싱 라이브러리 선택 (07-28)**:

- **PyMuPDF(+pymupdf4llm)** 채택. 결정 근거는 "가장 큰 실질 리스크가 2단 조판이고 거기서 쓸 도구가 더 낫다" 하나. 라이선스는 AGPL-3.0(듀얼) — 공개 레포·공개 이미지인 현 구조에선 고지 추가로 준수 가능하지만, 허용적 라이선스로 두거나 상용화하면 걸린다
- 그래서 **`pdf_parse.py` 어댑터 뒤에 격리**하는 게 선택 자체보다 중요 (`arxiv_api.py`와 같은 패턴). 라이선스나 품질 문제가 생기면 pypdfium2(Apache-2.0/BSD-3, PDFium 기반)로 함수 교체만으로 갈아끼운다 — 결정을 되돌릴 수 있게 만들어두는 쪽에 무게를 뒀다
- 제외: `marker`·`nougat` 등 ML 기반 파서는 torch를 다시 끌어와 이미지 8.77GB→2.04GB 작업을 무효화. GROBID(논문 특화, TEI XML로 references까지 구조화)는 Java 서비스라 t4g.micro(1GB)에 안 올라감 — 참고문헌 추출이 중요해지면 `profiles:`로 로컬 전용 옵션으로 재검토(llama-server와 같은 패턴)
- abstract는 LaTeX 조각이 섞인 평문(arXiv API `<summary>`가 저자 입력 그대로 — `$\alpha$`, `\sim` 등 + 하드랩). ②b 스크리닝엔 문제 없어 LaTeX 파싱 불필요, 공백·줄바꿈 정리만

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

**어디에 "좋은 모델로 검사"를 붙였나 — 그 판단 기준 (07-31)**:

예정 표의 일부 항목에만 **(좋은 모델로 검사 권장)**을 달았다. 전부 달면 신호가 희석되므로, **이 저장소에서 실제로 버그가 반복해서 나온 자리**를 기준으로 골랐다. 지금까지 발견된 버그들(07-14 fallback 후 교차 검증, 07-27 tool 라운드 예산, 07-28 `retrieve()` 2k·References 라벨·서지 복제, 07-31 `extract_abstract` 계층·요약 트리거 누락)을 놓고 보면 네 가지 패턴으로 수렴한다:

- **여러 모듈이 공유하는 계약** — 한쪽만 고치고 다른 쪽을 안 고쳐서 어긋난다(래퍼 노드 계약, 턴 경계).
- **식별자·상태 무결성** — `paper_id`·상태 전이처럼 틀려도 그 자리에서 안 터지고 한참 뒤에 조용히 잘못된 결과로 나타난다.
- **저장소·종류가 늘 때 필터 누락** — 컬렉션이나 `doc_type`이 하나 늘면 그걸 걸러야 할 곳 중 한 군데가 꼭 빠진다. `retrieve()` 2k 버그와 07-31 요약 트리거 누락이 같은 모양이다.
- **노드를 넘나드는 상태** — `disabled_models`·`try_count`처럼 여러 노드가 읽고 쓰는 값.

반대로 **안 단 항목들**의 공통점: 산출물을 눈으로 바로 확인할 수 있거나(요약 표시 형식, 아키텍처 그림), 실패해도 국소적이거나(tool 정비, 헤더 폴백), 애초에 실험이라 "정답"이 없다(자체 서빙 엔진, 학습 데이터 확장). 이런 건 리뷰보다 직접 돌려보는 게 빠르다.

**검사 시점도 중요하다** — 07-28·07-31 리뷰가 실제로 값어치 있었던 건 *구현 직후, 다음 기능을 얹기 전*에 했기 때문이다. 07-31에 발견한 `extract_abstract` 계층 버그는 07-28에 References에서 이미 고친 것과 같은 버그였는데도 사흘 뒤에 재현됐다 — **한 번 고친 버그 패턴이 다음 기능에서 되풀이되는지**를 보는 게 새 버그를 찾는 것만큼 중요하다는 뜻이다. 그래서 리뷰할 때는 완료 표의 버그 이력을 같이 훑는 편이 낫다.

## 방향성 메모

- 자기 챗봇 개선에만 집중하지 말고, 여러 기능을 써보며 공부에 활용: 챗봇 → RAG → 에이전트
- 멀티 **에이전트 개발**, **에이전트 서빙**(운영, → 자체 서빙 엔진 실험), 모델 튜닝은 할 줄 알아야
- 프레임워크 암기 X — 만들고자 하는 시스템을 어떻게 만드는지 참고 정도
- 바닐라 버전 / LangChain 버전 분리 유지 ("바닐라로 여기까지 했다")
