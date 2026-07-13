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
