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

## 🔄 진행 중

| 날짜 | 항목 | 상태 |
|---|---|---|
| 07-15~ | 베이스라인 완주 | gemini 쿼터 리필 대기 — bare gemini, graph(gemini-only)에서 역전 재현 확인 후 전체 비교표 완성 |

## 📅 예정

| 목표 시기 | 항목 | 내용 |
|---|---|---|
| 07-25 | HITL | `interrupt_before=["run_tools"]` — 안전 가드레일·논문 구매 승인 메커니즘의 예행연습 |
| 07-27 | 프론트엔드 | Streamlit 등 간이 UI (단기기억+쓰레드 안정화 후) |
| 07-29 | 멀티 에이전트 전환 1단계 | 현 그래프를 "물리 지식 에이전트" 서브그래프로 포장 (재작성 아님 — 컴파일된 그래프를 부모 그래프의 노드로) |
| 08-02 | 멀티 에이전트 전환 2단계 | 오케스트레이터(Supervisor 패턴) → 문헌 학습·평가(Evaluator-Optimizer, arxiv 선행) → 논문 조달(HITL) → 가설 수립 → 실험 설계(Plan-and-Execute) → 번역 레이어 |
| 08-06 | 장기기억 | VDB 메타데이터 필터링으로 user_id 태그 — 유저별 LTM 분리, 검증된 문헌의 LTM 승격 |
| 08-08 | verify 구성 비교 실험 확장 | self / 교차 / 무 verify / 다중 모델 앙상블 — correctness·토큰·지연 지표로 체계화 (현재 부분 진행: Qwen self-verify vs claude-verify 완료). 모든 에이전트 완성 후 전체 evaluation 단계에서 **bare vs graph 0.915 vs 0.926 차이의 반복 실행 신뢰도 검증(3회 이상 평균)**도 함께 진행 |
| 08-09 | 메시지 트리밍 | 멀티턴에서 messages 무한 성장 → 긴 대화의 generate 비용 관리 (tokens_used로 성장 측정 가능) |
| 08-10 | 후속 질문 재작성 | "그거 더 자세히" 같은 후속 질문이 그대로 벡터 검색어가 되는 문제 — 대화 맥락 기반 검색 질의 재작성 |
| 08-11 | SqliteSaver 영속화 | MemorySaver는 프로세스 메모리(재시작 시 소멸) → 디스크 영속화 |
| 08-12 | tool 정비 | wikipedia-api 기반 커스텀 tool(wikipedia 패키지 신뢰성 문제 대체), WolframAlpha 수식 검증 tool, arxiv API 이슈 해결 |
| 08-12 | tool 예외처리 잔여 | (핵심 제약·실패 3종 구분·서킷 브레이커·라운드 카운트·결과 길이 제한은 `run_tools`에 구현됨) **타임아웃**(네트워크 tool hang 대비 wrapper 레벨 제한), **관측성**(`tools_used`·`tool_errors` State 기록 → 디버그+verify 비교 지표), **보안 인지**(웹 검색 결과 프롬프트 주입 — 멀티 에이전트 가드레일과 함께 처리) |
| 08-13 | 학습 데이터 확장 | 45문항 → 파인만 강의록에서 대량 생성, 한국어 혼입(중국어 토큰) 대응, 데이터 비율 실험(논문 문어체 vs 평서문) |
| 08-14 | 개인 모델 2차 학습 | 확장 데이터로 재파인튜닝 → 젬마 등 가중치 공개 모델과 비교 평가 |

> 날짜 규칙: 완료 항목은 커밋 기준, 예정 항목은 착수 시 목표 시기를 채우고 완료 시 ✅ 표로 이동.

---

## 설계 노트 · 열린 질문

**Evaluator-Optimizer Pattern 효율성 의문** (꼬리 질문 체인):

- verify용 고급 검색을 어차피 한 번 하면, 처음부터 고급 검색으로 답하면 안 되나?
- vs 그러면 같은 context로 생성·검증 → "같은 책 읽은 바보가 바보를 검증"?
- verify만 좋은 모델? vs 그럴 거면 생성부터 좋은 모델?
- generate/verify 다른 모델? vs 처음부터 여러 모델 앙상블?

**멘토 답**: 관통하는 것은 "실험". "낫다"의 평가 기준을 수립한 뒤 각 가설(설정)을 실험해 비교하라. 개인 프로젝트에 이 실험·결과 분석이 스토리텔링으로 담기면 매력적. 라우팅 전략: 쉬운 일에 가벼운 모델 배치로 토큰 절약 가능(고급 모델은 토큰 단가 자체가 높음).

**→ 실험 설계** (예정 08-08과 연결): eval.json 31문항(카테고리·난이도 태깅, 미해결 3문항 포함) 기준으로 구성 비교 — (a) 단일 모델 self-verify (b) 교차 모델 verify(현재) (c) verify 없이 처음부터 고급 모델/고급 검색 (d) 다중 모델 종합. 지표: correctness 점수, 총 토큰, 지연시간.

## 방향성 메모

- 자기 챗봇 개선에만 집중하지 말고, 여러 기능을 써보며 공부에 활용: 챗봇 → RAG → 에이전트
- 멀티 **에이전트 개발**, **에이전트 서빙**(운영), 모델 튜닝은 할 줄 알아야
- 프레임워크 암기 X — 만들고자 하는 시스템을 어떻게 만드는지 참고 정도
- 바닐라 버전 / LangChain 버전 분리 유지 ("바닐라로 여기까지 했다")
