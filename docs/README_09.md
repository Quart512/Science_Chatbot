# 9주차 요약 — Qwen QLoRA 파인튜닝 + 양자화 + 로컬 서빙 통합

## 한 일

- Pydantic State 전환 (`TypedDict` → `BaseModel`, `.get()`/브래킷 접근 전부 `.attribute`로, 기본값·`Literal` 검증)
- tool 노드 분리 (generate 내부 while 루프 → `run_tools` 노드 + 조건 엣지) + tool 예외처리 (실패도 ToolMessage로 응답 → LLM 자가수정, 연속 2회 실패 시 서킷 브레이커)
- 파일 구조 기능별 분할: `models.py`(model_map + fallback) / `tool.py`(tool 레지스트리) / `retrieval.py`(임베딩+벡터스토어, ingest와 공유해 임베딩 모델 불일치를 구조로 방지)
- Qwen2.5-1.5B QLoRA 파인튜닝 → PTQ → GGUF → 로컬 서빙 통합 (아래 상세)
- **fallback 후 교차 검증이 깨지는 버그 수정**: verify는 원래 "생성 모델과 다른 모델이 검증"하도록 설계했는데, generate가 fallback으로 다른 모델로 갈아탄 경우 verify가 이를 몰라 `state.model`(요청 당시 모델) 기준으로만 회피해 생성자 본인이 검증하는 상황이 있었다. State에 두 필드를 분리해 추가:
  - `generated_by`: 실제로 이번 답변을 생성한 모델 (verify가 반드시 회피할 대상)
  - `disabled_models`: 이번 요청 안에서 이미 실패한 모델 목록 (재탐색으로 인한 낭비 호출 방지, 노드 경계를 넘어 State로 추적)
  - 회피 대상(`models_skip`, 호출마다 새로 정함)과 고장 목록(`disabled_models`, 실패 시 누적)을 별도 파라미터로 분리 — 합쳐서 관리하면 "이번엔 피하고 싶을 뿐"과 "완전히 죽었음"이 뒤섞여 생성자가 영구 배제될 수 있음
  - 우선순위: 교차 검증 → 후보 소진 시 생성자 자가 검증 → 전 모델 소진 시 verify 생략 (에러로 터뜨리지 않음)
- evaluate.py에 평가 대상 선택(`--target graph|gemini|claude|Qwen-tuned`) + 저장 이름 분리(`--name`) 추가. 채점자(judge)는 claude-haiku로 전 실행 고정 — 채점자가 바뀌면 실행 간 비교가 오염되기 때문 (처음엔 gemini judge였으나 무료 등급 쿼터 20회/일로 31문항 채점 불가라 교체)

## 파인튜닝 · 양자화

**QLoRA 파인튜닝**: Qwen2.5-1.5B, r=16, `train_qa.json` 45문항(파인만 강의록 기반), 6에폭 — loss 3.51 → 0.21

<details>
<summary>Training loss 로그 (step 5~70)</summary>

| Step | Loss | | Step | Loss |
|---|---|---|---|---|
| 5 | 3.510 | | 40 | 0.657 |
| 10 | 2.107 | | 45 | 0.548 |
| 15 | 1.474 | | 50 | 0.437 |
| 20 | 1.230 | | 55 | 0.352 |
| 25 | 1.186 | | 60 | 0.304 |
| 30 | 0.932 | | 65 | 0.238 |
| 35 | 0.822 | | 70 | 0.209 |

</details>

**PTQ 비교 + GGUF 변환(Q4_K_M)**:

| precision | load_time_s | infer_time_s | memory_gb | avg_score |
|---|---|---|---|---|
| fp16 | 60.5 | 12.2 | 3.10 | 0.058 |
| int8 | 22.9 | 49.1 | 1.84 | 0.025 |
| int4 | 13.9 | 19.1 | 1.26 | 0.025 |

**로컬 서빙**: GGUF(941MB)를 llama-server(llama.cpp, OpenAI 호환 로컬 서버)로 서빙, `model_map["Qwen-tuned"]` 등록. 서버 접속 에러(`APIConnectionError`)도 fallback 체인에 포함 — 로컬 모델이 죽으면 API 모델로 자동 전환.

## 평가 실험

held-out 31문항 (`evaluation/eval.json`), 채점: claude-haiku (LLM-as-judge, 전 실험 고정).

### 종합 비교

| 구성 | 전체 평균 | 비고 |
|---|---|---|
| bare Qwen-tuned (Q4) | 0.132 | 파인튜닝 모델 단독 |
| graph + Qwen (verify도 Qwen) | 0.176 | 구조(ReAct+Evaluator-Optimizer)만의 효과 |
| graph + Qwen (verify=claude) | 0.445 | 좋은 verifier의 효과 |
| graph 기본 (gemini→claude fallback) | 0.813 | 프롬프트 개선 전 |
| graph 기본 + 프롬프트 개선 | 0.827 | |
| graph(claude 고정, gemini 혼입 제거, judge temp=0) | 0.910 | bare와 거의 동일 — 남은 차이는 "측정 문제" 단일 문항 (실험 4) |
| bare claude-haiku | 0.915 | 최고점 |

카테고리별:

| 카테고리 | bare Qwen | graph+Qwen (self-verify) | graph+Qwen (verify=claude) | graph 기본 (개선 후) |
|---|---|---|---|---|
| atomic | 0.210 | 0.320 | 0.410 | 0.910 |
| electromagnetism | 0.150 | 0.138 | 0.575 | 0.700 |
| mechanics | 0.190 | 0.090 | 0.720 | 0.870 |
| open_problem | 0.150 | 0.117 | 0.583 | 0.707 |
| quantum | 0.100 | 0.310 | 0.380 | 0.804 |
| relativity | 0.090 | 0.130 | 0.380 | 0.890 |
| thermodynamics | 0.025 | 0.075 | 0.075 | 0.838 |
| **전체** | **0.132** | **0.176** | **0.445** | **0.827** |

### 실험 1 — 반복 루프 버그 (graph+Qwen 첫 실행)

graph-Qwen으로 돌리던 중 Qwen이 같은 구절을 무한 반복하며 혼자 33K 토큰을 생성:

> 그 파동이 특정 빛의 색으로 인식되는 특수한 조건이 필요한 때문이 아니라, 그 파동이 특정 빛의 색으로 인식되는 특수한 조건이 필요한 때문이 아니라, … (반복)

연쇄 장애까지 이어짐: verify(claude)가 이상을 감지하고 재생성을 요청했으나 33K짜리 이전 응답이 AIMessage로 대화 이력에 들어가면서 llama-server가 bad request로 다운 → 이후는 fallback 체인(claude 생성 → gemini verify → gemini 쿼터 소진 → claude 자가 검증)으로 진행.

**원인 분석**: 튜닝된 Qwen의 과적합 + greedy decoding(temperature=0)이 "~때문이 아니라 → 그 파동이~"의 순환 구조를 만들어냄.

**대응**:
- `frequency_penalty=0.3` — 이미 나온 토큰의 확률을 깎는 OpenAI API 파라미터
- `max_tokens=10K` 제한

### 실험 2 — 구조가 약한 모델을 얼마나 구제하는가

- bare Qwen 0.129 → graph+Qwen(verify=claude) **0.445**. 다만 이건 claude가 verifier로 개입한 결과라 변인통제에 한계가 있어, verify까지 Qwen으로 돌리는 추가 실험 진행
- graph+Qwen(self-verify) **0.144** — 구조(ReAct + Evaluator-Optimizer)만의 순수 효과는 +0.015에 그침
- 결론: **점수 상승의 대부분은 verifier의 품질에서 옴.** claude가 what_to_fix로 사실상 정답을 알려주는 문항도 관찰됨 — verify는 검증자이자 은근한 지식 주입 경로

### 실험 3 — 강한 모델에는 파이프라인이 오히려 해로움

bare claude **0.905** > graph 기본 **0.813**. 원인 분석: ReAct·Evaluator-Optimizer를 거치며 이미 messages에 있던 정확한 내용이 최종본에서 누락되거나, 품질 낮은 RAG 청크·웹 검색 결과가 참고되면서 garbage in–garbage out.

실패 사례 (score 0.0): "원자의 화학적 정체성을 결정하는 것은?" — 정답 "핵 속의 양성자 수"인데, graph는 RAG 문서의 "화학적 성질은 전자의 개수가 결정" 구절에 끌려가 "전자의 개수"로 답변.

**프롬프트 개선**: 아는 것 중심으로 답하고 검색·문서는 참고로만 쓰도록 강조 → 0.813 → **0.827**. 여전히 bare claude(0.905)에는 못 미침.

**단, 비교에 구조적 불리함이 있음**: bare claude는 claude만으로 돌지만 graph 기본은 gemini로 돌다가 쿼터 소진 시 claude로 넘어가는 혼합 구성. gemini 단독 성능이 0.827 이하라면 "구조가 성능을 개선"이라는 해석이 성립한다 → **gemini-only 테스트 필요** (쿼터 리필 후).

### 실험 4 — graph를 claude로만 고정(gemini 혼입 제거)했을 때

> bare claude의 0.905→0.915 변동은 judge(`judge_llm`)의 temperature가 고정되지 않아 생긴 채점 비결정성 문제로 확인 — `temperature=0`으로 수정.

실험 3의 "bare claude(0.905) > graph 기본(0.827)" 비교는 graph 기본이 gemini→claude fallback **혼합** 구성이라 변인통제가 안 됐다. graph 전체를 claude 고정(`disabled_models: ["gemini", "Qwen-tuned"]`)으로 다시 측정:

| 구성 | 전체 평균 | solved 평균 | unsolved 평균 |
|---|---|---|---|
| bare claude | 0.915 | 0.917 | 0.890 |
| graph(claude 고정) — judge temp 고정 전 | 0.897 | 0.917 | 0.707 |
| graph(claude 고정) — judge temp=0 재측정 | **0.910** | 0.917 | **0.840** |

judge 온도를 고정하고 다시 재보니 전체 평균은 bare(0.915)와 거의 같아졌다(0.910). solved는 애초부터 동률(0.917)이고, unsolved도 0.707 → 0.840으로 크게 좁혀졌다. 하지만 완전히 같아지진 않았다 — unsolved 3문항을 개별로 보면 원인이 훨씬 좁게 좁혀진다:

| 미해결 문항 | bare claude | graph(claude) |
|---|---|---|
| 암흑물질의 정체는 무엇인가? | 0.92 | 0.92 |
| 양자역학과 일반상대성이론은 어떻게 통합되는가? | 0.90 | **0.95**(graph가 더 높음) |
| 양자역학의 측정 문제란 무엇인가? | 0.85 | **0.65**(유일하게 낮음) |

즉 unsolved 평균이 낮아 보였던 건 사실상 **31문항 중 "측정 문제" 딱 하나**의 문제였다(0.35→0.65로 judge 온도 고정만으로도 절반쯤 개선됐지만, bare의 0.85에는 여전히 못 미침). 암흑물질·양자중력 통합은 graph가 bare와 동등하거나 더 잘한다.

**왜 유독 "측정 문제"만 걸리는가**: 암흑물질·양자중력 통합도 파인만 강의(1960년대)엔 당연히 없는 주제라 retrieve는 이 질문들에도 무관한 문서를 끌어왔을 것이다. 그런데 그 경우는 모델이 "이 문서는 질문과 상관없다"고 쉽게 판단하고 자기 지식으로 전환해 오히려 정확하게 "미해결"이라고 답한 것으로 보인다. 반면 "측정 문제"에서 끌려온 문서(EPR 역설, 불확정성 원리 — 파인만 강의 8770/12851/3875번)는 **완전 무관하진 않고 오히려 꽤 그럴듯하게 관련있어 보이는 인접 주제**라서 더 위험하다. 완전히 무관한 검색 결과는 모델이 쉽게 무시하지만, "절반만 맞는" 근접 검색 결과는 그 자체로 그럴듯한 답을 만들 재료가 되어 모델을 엉뚱하지만 자신감 있는 방향으로 이끈다.

**개선 아이디어(갱신)**:
1. 이제 문제는 "open_problem 카테고리 전반"이 아니라 **"토픽은 인접하지만 질문의 핵심 쟁점은 다루지 않는 근접 검색 결과"**로 좁혀졌다 — 코퍼스 확장보다 이 근접-오검색 케이스를 다루는 게 더 정밀한 해법
2. `generate` 시스템 프롬프트에 "검색된 문서가 질문의 핵심 쟁점(여기선 해석 논쟁)을 직접 다루지 않는다면, 문서에 없는 네 지식으로 그 쟁점을 보완해라"는 문구 추가 — "문서를 참고해서 답해"만으로는 근접하지만 불완전한 문서에 과도하게 종속됨
3. `verify`에 "검색된 문서가 질문에 실제로 답하는가"를 먼저 판정하는 체크를 추가 — 지금은 답변의 사실관계만 보고 "문서가 애초에 이 질문의 핵심을 다루는지"는 안 봄
4. 코퍼스 확장은 우선순위를 낮춰도 됨 — 암흑물질·양자중력처럼 아예 무관한 경우는 이미 잘 처리되고 있음이 확인됐기 때문


### 실험 5 — 출력 이원화: answer / comment 채널 분리

**문제 발견**: graph(claude) 저득점 문항을 분석하니, 내용은 정확한데 0.15를 받은 사례가 있었다 ("파동-입자 이중성"). 원인 연쇄:

1. verify가 "답변은 정확하다"고 말하면서도 **문서 근거성**(내용이 RAG 문서에 없음)을 이유로 fix_needed=True를 반복 → 정확한 답이 3라운드 반려
2. 3번째 재시도에서 모델이 대화 관성으로 **프리앰블**("제 판단을 유지하겠습니다. 앞의 답변이...")을 답변 앞에 붙임
3. judge가 프리앰블 섞인 답변을 채점 → 0.15

또한 limit 도달 시 답변에 코드가 덧붙이던 실패 고지("limit:N 내 도출 불가...")도 같은 방식으로 점수를 오염시키고 있었다 — **사용자에겐 필요한 정보가 측정에는 노이즈**인 상황.

**수정 3종**:

1. **verify 판정 기준 명시** — fix_needed는 사실 오류·질문 불일치일 때만 True, "문서에 근거 없음"은 반려 사유가 아님 (시스템 프롬프트 + Field description 양쪽에). verify 스키마에 `comment` 필드를 추가해 검증자의 부가 발언이 what_to_fix(반려 트리거)로 새지 않도록 **배출구** 마련
2. **재시도 프롬프트 개선** — "타당하면 반영하고, 아니면 네 판단을 유지해도 된다. 최종 답변만 다시 제시해" (프리앰블의 심리적 원인 제거)
3. **출력 이원화** — 사용자에게는 answer(본문)와 comment(부가 정보)를 모두 주고, **평가는 answer만** 채점:
   - `final_answer` 노드에서 초안을 `{final_answer, comment}` structured output으로 분리. 단 **try_count > 1일 때만** (프리앰블은 재시도 대화에서만 생기므로, 첫 통과 답변은 추출 호출 없이 그대로 — 평시 추가 비용 0)
   - **시스템 comment**는 LLM이 아니라 코드가 작성 (limit 도달, fallback 발생 등 — State에 있는 사실의 f-string 조립)
   - description 핵심 규칙: "세계의 불확실성(미해결·논쟁)은 answer 본문에, 모델 자신의 불확실성(확신 부족·판단 과정)은 comment에" — 미해결 인정이 comment로 빠지면 unsolved 채점 기준을 통과 못 하기 때문
   - API 응답이 `{"answer": ..., "comment": ...}`로 확장

**실전 확인 (graph+Qwen, limit 도달 케이스)**: 4회 재시도 모두 실패한 뒤에도 comment가 "limit:4 내 도출 불가 + 남은 문제점 + limit/top_k 증가·다른 모델 재시도 권장"을 정확히 전달 — **답은 틀렸지만 시스템은 정직했다.** 출력 이원화가 목적대로 작동한 첫 사례.

**추출자 관찰과 설계 결정**: 추출(분리)을 `generated_by` 모델에게 맡기는데, Qwen-tuned가 추출자일 때 "분리만 하라"는 지시를 무시하고 초안에 없던 내용을 창작하는 현상 확인 — structured output의 **형식**은 서버가 강제하지만 **지시 준수**는 모델 능력에 달렸다. 추출자를 강한 모델로 교체하는 안도 검토했으나 **기각**: 모델 선택 기능의 목적이 토큰 절약인데 추출만 예외로 강한 모델을 쓰면 "약한 모델을 안 쓰는 것"과 다를 바 없고, comment 채널이 실패를 정직하게 고지하므로 수용 가능. 추후 gemini/claude가 generated_by인 재시도 케이스에서 추출·comment 품질을 확인 예정.

**부가 발견 2건**:

- **Qwen은 verify 지적을 반영하지 못한다** — 같은 질문에 4회 연속 거의 동일한 답(측정 문제에선 글자 하나 안 바뀜). Evaluator-Optimizer 루프는 "고칠 능력이 있는 모델"에만 작동한다는 것의 직접 증거 (실험 2에서 구조 효과가 +0.015에 그친 메커니즘)
- **verify 판정의 비결정성** — 동일 답·동일 verifier(gemini)인데 3회 True 후 4회째 False. model_map 모델들의 temperature가 기본값이라 판정이 흔들림 → 실험 재현성 위해 temperature=0 고정 검토

## 장애 복원력 테스트

llama-server를 꺼둔 채(Qwen-tuned 접속 불가) + gemini 쿼터가 이미 소진된 상태에서 질문("what is gravity")을 던져 의도치 않게 이중 장애 시나리오가 만들어졌다. 로그로 확인된 동작:

1. Qwen-tuned 접속 실패 → gemini 시도 → 쿼터 초과 → claude가 최종 생성 (2단 fallback)
2. tool 호출(search_wikipedia) 왕복 후 재진입한 generate가 죽은 Qwen-tuned·gemini에 재요청 없이 곧장 claude로 — `disabled_models`가 State에 남아 있어 이미 죽은 모델을 다시 두드리지 않음
3. verify가 [claude(생성자), Qwen-tuned(고장), gemini(고장)]를 모두 회피 대상으로 계산 → 후보 없음 → 설계한 차순위 경로대로 생성자(claude) 본인이 검증

의도한 정상 경로(다른 모델이 교차 검증)가 아니라 최후 방어선(차순위: 생성자 자가 검증)이 발동한 것이지만, 정확히 설계한 대로 동작했다. fallback 체인·모델별 서킷 브레이커·교차 검증 우선순위가 실제 장애 조합에서 전부 검증된 사례. 이후 verify 단계에서 모든 모델이 소진되면 에러로 터뜨리는 대신 verify를 생략하는 브랜치를 추가했다.

## 통찰

- 학습 loss는 잘 떨어졌지만 held-out 평가 점수는 낮음 — 과적합 의심, 45문항은 일반화엔 부족. loss 하강 곡선만 보고 안심하면 안 된다는 걸 수치로 확인
- 세 정밀도(fp16/int8/int4) 정답률이 비슷하게 낮음 → 양자화 문제가 아니라 파인튜닝 데이터 부족 + Qwen의 약한 한국어 능력이 원인 (답변에 중국어 혼입 확인)
- 학습 데이터(train_qa.json 45문항)와 평가 데이터(eval.json 31문항)를 분리해둔 것이 유효했다 — 겹쳤으면 과적합을 성능으로 착각했을 것
- **에이전트 구조의 효과는 베이스 모델의 강함에 반비례**: 약한 모델(Qwen)은 구조+좋은 verifier로 3.4배 상승(0.132→0.445), 강한 모델(claude)은 오히려 하락(0.905→0.827) — 파이프라인은 공짜가 아니고, 저품질 컨텍스트 주입 경로이기도 하다
- verifier는 검증자이자 지식 주입 경로 — 교차 검증 실험에서 verify 모델의 품질이 최종 점수의 지배 변수였음
- Unsloth가 `transformers`를 프로세스 메모리에 몬키패치 → 학습/PTQ 노트북 분리 + Google Drive 경유로 해결 (Colab 로컬 디스크는 세션 간 영속성 없음)
- 성능은 낮지만 비교군으로서의 가치는 충분: "1.5B 파인튜닝 모델이 프론티어 모델 대비 어디까지 되고 어디서 무너지는가"
- **측정 대상과 사용자 전달 내용은 분리해야 한다** — 실패 고지·확신 수준 같은 메타 정보는 사용자에겐 가치, judge에겐 노이즈. answer/comment 이원화로 둘 다 지킴 (실험 5)
- **구조의 부품(verify 지적 반영, 추출)은 모델의 지시 추종 능력을 전제한다** — 능력 없는 모델에겐 루프도 추출도 무력하거나 역효과. 파이프라인 설계는 "어떤 모델이 이 자리에 올 수 있는가"까지 포함해야 함

## 남은 과제

- gemini-only 테스트 (쿼터 리필 후) — bare gemini vs graph(gemini) 로 "구조의 개선 효과" 최종 판정
- gemini/claude가 generated_by인 재시도 케이스에서 추출·comment 품질 확인 (실험 5 후속)
- 동일 답 조기 종료 — 재시도 답변이 이전과 같으면 verify 재호출 없이 final_answer 직행 (verify 쿼터 절약, 문자열 비교 한 줄)
- model_map 모델들 temperature=0 고정 검토 (verify 판정 비결정성 대응, 실험 재현성)
- 단기기억/쓰레드 (checkpointer), HITL, 프론트, 오케스트레이터 및 에이전트들 구성
- 학습 데이터 확장 (45문항 → 파인만 강의록에서 대량 생성) 및 한국어 혼입 문제 대응
