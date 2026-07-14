# 9주차 요약 — Qwen QLoRA 파인튜닝 + 양자화 + 로컬 서빙 통합

## 한 일

- Pydantic State 전환 (`TypedDict` → `BaseModel`, `.get()`/브래킷 접근 전부 `.attribute`로, 기본값·`Literal` 검증)
- tool 노드 분리 (generate 내부 while 루프 → `run_tools` 노드 + 조건 엣지) + tool 예외처리 (실패도 ToolMessage로 응답 → LLM 자가수정, 연속 2회 실패 시 서킷 브레이커)
- 파일 구조 기능별 분할: `models.py`(model_map + fallback) / `tool.py`(tool 레지스트리) / `retrieval.py`(임베딩+벡터스토어, ingest와 공유해 임베딩 모델 불일치를 구조로 방지)
- Qwen2.5-1.5B QLoRA 파인튜닝 (r=16, `train_qa.json` 45문항 — 파인만 강의록 기반, 6에폭) — loss 3.51 → 0.21

  | Step | Training Loss |
  |---|---|
  | 5 | 3.509673 |
  | 10 | 2.107224 |
  | 15 | 1.473569 |
  | 20 | 1.229633 |
  | 25 | 1.186154 |
  | 30 | 0.931888 |
  | 35 | 0.821883 |
  | 40 | 0.657081 |
  | 45 | 0.547903 |
  | 50 | 0.436967 |
  | 55 | 0.352090 |
  | 60 | 0.303662 |
  | 65 | 0.238255 |
  | 70 | 0.208656 |

- PTQ 비교 (FP16/INT8/INT4) + GGUF 변환(Q4_K_M)

  | precision | load_time_s | infer_time_s | memory_gb | avg_score |
  |---|---|---|---|---|
  | fp16 | 60.5 | 12.2 | 3.10 | 0.058 |
  | int8 | 22.9 | 49.1 | 1.84 | 0.025 |
  | int4 | 13.9 | 19.1 | 1.26 | 0.025 |

- GGUF(941MB)를 llama-server(llama.cpp, OpenAI 호환 로컬 서버)로 서빙하고 `model_map["Qwen-tuned"]`로 챗봇에 등록. 서버 접속 에러(`APIConnectionError`)도 fallback 체인에 포함 — 로컬 모델이 죽으면 API 모델로 자동 전환
- **fallback 후 교차 검증이 깨지는 버그 수정**: verify는 원래 "생성 모델과 다른 모델이 검증"하도록 설계했는데, generate가 fallback으로 다른 모델로 갈아탄 경우 verify가 이를 몰라 `state.model`(요청 당시 모델) 기준으로만 회피해 생성자 본인이 검증하는 상황이 있었다. 이를 고치기 위해 State에 두 필드를 분리해 추가:
  - `generated_by`: 실제로 이번 답변을 생성한 모델 (verify가 반드시 회피할 대상)
  - `disabled_models`: 이번 요청 안에서 이미 실패한 모델 목록 (재탐색으로 인한 낭비 호출 방지, 노드 경계를 넘어 State로 추적)
  - 회피 대상(`models_skip`, 요청마다 새로 정함)과 고장 목록(`disabled_models`, 실패 시 누적)을 별도 파라미터로 분리 — 합쳐서 관리하면 "이번엔 피하고 싶을 뿐"과 "완전히 죽었음"이 뒤섞여 생성자 자신이 영구 배제될 수 있음
  - 모든 fallback 후보가 소진되면 차순위로 생성자 본인이 검증 (교차 검증 > 없음)
- evaluate.py에 평가 대상 선택(`--target graph|gemini|claude|Qwen-tuned`) + 저장 이름 분리(`--name`, 양자화 전/후 구분용) 추가. 채점자(judge)는 claude-haiku로 전 실행 고정 — 채점자가 바뀌면 실행 간 비교가 오염되기 때문 (처음엔 gemini judge였는데 무료 등급 쿼터 20회/일로는 31문항 채점이 불가능해서 교체)

## 평가 결과 — Qwen-tuned (Q4_K_M, held-out 31문항)

전체 평균 **0.132** (채점: claude-haiku, LLM-as-judge)

| 카테고리 | 평균 | n |
|---|---|---|
| atomic | 0.210 | 5 |
| mechanics | 0.190 | 5 |
| electromagnetism | 0.150 | 4 |
| open_problem | 0.150 | 3 |
| quantum | 0.100 | 5 |
| relativity | 0.090 | 5 |
| thermodynamics | 0.025 | 4 |

일반 문항 0.13 / 미해결 문항 0.15. gemini·claude 베이스라인과 graph(RAG+verify) 구성 비교는 진행 예정 — 특히 "약한 모델을 파이프라인이 얼마나 구제하는가"(bare Qwen vs graph+Qwen)가 다음 실험의 핵심 질문.

## 장애 복원력 테스트

llama-server를 꺼둔 채(Qwen-tuned 접속 불가) + gemini 쿼터가 이미 소진된 상태에서 질문("what is gravity")을 던져 의도치 않게 이중 장애 시나리오가 만들어졌다. 로그로 확인된 동작:

1. Qwen-tuned 접속 실패 → gemini 시도 → 쿼터 초과 → claude가 최종 생성 (2단 fallback)
2. tool 호출(search_wikipedia) 왕복 후 재진입한 generate가 죽은 Qwen-tuned·gemini에 재요청 없이 곧장 claude로 — `disabled_models`가 State에 남아 있어 이미 죽은 모델을 다시 두드리지 않음
3. verify가 [claude(생성자), Qwen-tuned(고장), gemini(고장)]를 모두 회피 대상으로 계산 → 후보 없음 → 설계한 차순위 경로대로 생성자(claude) 본인이 검증

의도한 정상 경로(다른 모델이 교차 검증)가 아니라 최후 방어선(차순위: 생성자 자가 검증)이 발동한 것이지만, 정확히 설계한 대로 동작했다. fallback 체인·모델별 서킷 브레이커·교차 검증 우선순위가 실제 장애 조합에서 전부 검증된 사례.

## 통찰

- 학습 loss는 잘 떨어졌지만 held-out 평가 점수는 낮음 — 과적합 의심, 45문항은 일반화엔 부족. loss 하강 곡선만 보고 안심하면 안 된다는 걸 수치로 확인
- 세 정밀도(fp16/int8/int4) 정답률이 비슷하게 낮음 → 양자화 문제가 아니라 파인튜닝 데이터 부족 + Qwen의 약한 한국어 능력이 원인 (답변에 중국어 혼입 확인)
- 학습 데이터(train_qa.json 45문항)와 평가 데이터(eval.json 31문항)를 분리해둔 것이 유효했다 — 겹쳤으면 과적합을 성능으로 착각했을 것
- Unsloth가 `transformers`를 프로세스 메모리에 몬키패치 → 학습/PTQ 노트북 분리 + Google Drive 경유로 해결 (Colab 로컬 디스크는 세션 간 영속성 없음)
- 성능은 낮지만 비교군으로서의 가치는 충분: "1.5B 파인튜닝 모델이 프론티어 모델 대비 어디까지 되고 어디서 무너지는가"

## 남은 과제

- 베이스라인 완주 (gemini·claude bare + graph 구성별) → compare.py로 카테고리별 비교표
  results/eval_ 에 모델별 결과 저장. gemini 2.5 flash 사용량 복구되면 graph, gemini target으로 진행
- 단기기억/쓰레드 (checkpointer), HITL, 프론트, 오케스트레이터 및 에이전트들 구성
- 학습 데이터 확장 (45문항 → 파인만 강의록에서 대량 생성) 및 한국어 혼입 문제 대응
