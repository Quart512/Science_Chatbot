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
## 평가 결과 - graph(Qwen+verify as claude)

1. graph-Qwen으로 돌리다가 흥미로운 버그 발견
그 파동이 특정 빛의 색으로 인식되는 특수한 조건이 필요한 때문이 아니라, 그 파동이 특정 빛의 색으로 인식되는 특수한 조건이 필요한 때문이 아니라, 그 파동이 특정 빛의 색으로 인식되는 특수한 조건이 필요한 때문이 아니라, 그 파동이 특정 빛의 색으로 인식되는 특수한 조건이 필요한 때문이 아니라,

이렇게 반복되는 루프가 걸리면서 Qwen이 지혼자 33K 반복. verify에서 claude가 이상함 확인하고 qwen에게 재생성 쿼리 넣었으나 그 과정에서 이전 응담(33k)이 AImessage로 들어감->llama server 다운, bad request 에러나면서 나머지는 fallback인 claude가 생성 후 gemini가 verify하는 것으로 의도와 다르게 진행됨(진행하면서 gemini의 사용량 제한으로 claude가 생성, claude가 verify하는 검증으로 나아감)

이를 튜닝한 qwen의 과적합과 greedy decoding(temp=0) 때문이라고 분석, 때문이 아니라~ 다음에 그 파동이~ 이 순환구조로 연결되어버림.
이를 고치기 위해 
- 이미 나온 토큰의 확률을 깎는 frequency_penalty=0.3 openai api의 파라메터로 추가
- max_token=10k로 제한함.

2. 정상 평가 결과
=== 평가 요약 ===
전체: 평균 0.445 (n=31)
일반 문항: 평균 0.430 (n=28)
미해결 문항(인정+사실정확성): 평균 0.583 (n=3)

카테고리별 평균:
  atomic: 평균 0.410 (n=5)
  electromagnetism: 평균 0.575 (n=4)
  mechanics: 평균 0.720 (n=5)
  open_problem: 평균 0.583 (n=3)
  quantum: 평균 0.380 (n=5)
  relativity: 평균 0.380 (n=5)
  thermodynamics: 평균 0.075 (n=4)

3. bare Qwen vs graph+Qwen 비교
{'eval_qwen-tuned-q4.json': 0.13225806451612898, 'eval_claude.json': 0.9045161290322578, 'eval_graph-Qwen.json': 0.44516129032258067, 'eval_graph.json': 0.8135483870967742}

0.132->0.445로 증가한 것으로 보임
하지만 이건 Qwen 모델만 사용한 것이 아니라 verifier로서 claude를 사용했기 때문에 변인통제에 한계가 있다. 
verify마저 qwen으로 진행하는 실험 진행중

## 평가 결과 - Qwen-tuned, claude, graph(claude), graph(Qwen+verify as claude)
gemini 2.5 flash는 사용량 제한으로 진행하지 못했음

{'eval_qwen-tuned-q4.json': 0.13225806451612898, 
'eval_claude.json': 0.9045161290322578, 
'eval_graph-Qwen.json': 0.44516129032258067, 
'eval_graph.json': 0.8135483870967742}

주목할 점은 eval_claude.json 보다 eval_graph.json이 하락했다는 점이다.
ReAct와 Evaluator-Optimizer 패턴을 거치면서 
최종본에 이미 message에 있는 내용이 누락되거나, 퀄리티 낮은 rag나 웹 검색 툴의 결과가 참고되면서 garbage in-garbage out이 된것으로 보임
프롬프트를 다듬어 자신이 알고있는것 중점으로 대답하고, 나머지는 참고할것을 강조하고, 주어진 맥락과 별개로 항상 최종 답변을 structured output으로 추출하는 방식으로 진행 후 latest version으로 재비교 해보기
아래는 eval_graph의 예시
  {
    "question": "원자의 화학적 정체성을 결정하는 것은?",
    "answer": "핵 속의 양성자 수",
    "category": "atomic",
    "difficulty": "basic",
    "unsolved": false,
    "prediction": "제공된 문서에서 답을 찾을 수 있습니다.\n\n문서의 내용에 따르면:\n\n**원자의 화학적 정체성(화학적 성질)을 결정하는 것은 전자(electrons)의 개수입니다.**\n\n문서에서 명시적으로 다음과 같이 설명하고 있습니다:\n\n> \"원자의 화학적 성질은 전자의 개수에 의해 결정되며, 핵의 질량에 의해 결정되지 않는다.\"\n\n이는 같은 원소라 하더라도 중성자의 개수가 다를 수 있다는 것을 의미합니다. 예를 들어, 탄소(carbon)의 경우 6개의 양성자는 동일하지만, 6개 또는 7개의 중성자를 가질 수 있습니다(이것이 동위원소). 하지만 전자의 개수(양성자와 같음)가 같기 때문에 화학적 성질은 동일합니다.",
    "score": 0.0
  }, 

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
