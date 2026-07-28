# README_12 — 배포 전 테스트 게이트 · 프론트엔드(Streamlit) · verify 단기기억 버그 수정 · 아키텍처 개편

## 1. 배포 전 테스트 게이트 (CI)

(README_11에서 다룬 내용과 중복이지만 이번 세션 변경 이력에 포함되어 다시 짧게 적는다.)

`.github/workflows/deploy.yml`을 `test` / `deploy` 두 job으로 분리했다. `test` job이 `uv sync` + `uv run pytest`(4개 톨게이트 테스트)를 돌리고, `deploy` job은 `needs: test`로 걸려 있어 테스트 실패 시 이미지 빌드·EC2 배포 자체가 시작되지 않는다. EC2 배포 스크립트에는 `docker image prune -f`도 추가해 배포 때마다 쌓이는 옛 이미지를 자동 정리하게 했다.

### CI가 실제로 게이트 역할을 한 사례

`turn_start_len` 필드(아래 4번)를 `State`에 추가하면서, `tests/test_reset_turn.py`의 `EXPECTED_RESET` 고정 딕셔너리를 갱신하는 걸 깜빡했다. 이 테스트는 애초에 "State에 필드 추가하고 `reset_turn` 갱신을 깜빡한 경우를 잡는 안전망"이라고 docstring에 적어뒀던 바로 그 테스트인데, 실제로는 반대 방향(코드는 맞게 고쳤는데 테스트 쪽을 안 고침)으로 걸렸다. 로컬 확인 없이 바로 push했다가 GitHub Actions의 `test` job에서 실패(`AssertionError`, `turn_start_len` 키 누락)로 잡혔고, `deploy` job은 `needs: test` 덕분에 아예 시작도 안 됐다 — 정확히 이 게이트를 만든 목적대로 동작한 사례. `EXPECTED_RESET`에 `turn_start_len: 0` 추가 + `turn_start_len`이 실제로 `len(state.messages)`를 정확히 반영하는지 검증하는 테스트를 하나 더 추가해서 해결했다.

## 2. 프론트엔드(Streamlit) 도입

`/docs`(Swagger UI)로만 API를 두드려볼 수 있던 걸 대체할 최소 채팅 UI를 Streamlit으로 붙였다(`frontend/app.py`). 백엔드와 완전히 분리된 별도 서브프로젝트(`frontend/pyproject.toml`·`uv.lock`·`Dockerfile`)로 만들었다 — 백엔드는 이미 8.77GB → 2.04GB로 줄여둔 이미지라, Streamlit의 무거운 의존성 트리를 얹으면 그 작업이 무의미해지기 때문(`llama-server`를 별도 이미지로 분리했던 것과 같은 이유). `thread_id`를 세션당 한 번만 발급해 유지하고, 요청 페이로드는 `main.py`의 `Query` 스키마와 맞춰 백엔드 단기기억(`MemorySaver`)이 그대로 이어지게 했다.

## 3. 프론트 컨테이너 분리 + docker-compose 통합

`docker-compose.yml`에 `frontend` 서비스를 `profiles: ["frontend"]`로 추가했다 — `llama-server`와 같은 패턴으로, API만으로도 충분하니 기본 `up`엔 안 뜨고 `--profile frontend up`으로 선택 설치. `depends_on`은 한때 `condition: service_healthy` + healthcheck(10초마다 내부에서 `/docs` GET)까지 붙여봤지만, 유휴 상태에서도 로그가 계속 쌓이는 게 거슬리고 개인 프로젝트 규모에 과한 엄밀함이라 판단해 순서만 보장하는 평범한 `depends_on`으로 되돌렸다. 이미지 크기는 프론트 760MB(컨텐츠 173MB) vs 백엔드 2.04GB(컨텐츠 418MB)로, 분리 효과(무거운 langchain 계열 의존성 미포함)를 확인했다.

### CI/CD에도 프론트를 포함시키기로 결정

처음엔 "기본값은 프론트 없이, 필요할 때만 EC2에서 수동으로 `--profile frontend`로 설치"하는 쪽으로 `deploy.yml`을 짰다. 근데 실제로 로컬에서 `docker-compose.yml`을 EC2로 매번 손으로 옮기고 `--profile frontend`를 매번 붙여야 하는 게 귀찮을 것 같아서, 마음을 바꿔 **CI가 백엔드와 프론트를 항상 같이 배포**하도록 정리했다:

- `deploy.yml`에 프론트 이미지 빌드+push 스텝 추가(`context: ./frontend`, 태그 `quart512/science-chatbot-frontend:latest`)
- `docker-compose.yml`을 EC2로 자동 전송하는 스텝 추가(`appleboy/scp-action`) — git의 최신 파일을 그대로 옮기므로 `frontend` 서비스 정의가 항상 EC2에도 반영됨
- EC2 배포 스크립트를 `docker compose --profile frontend pull` + `up -d`로 변경

과정에서 오타 하나(`tags: quart512/science-chatbot:` — `latest` 누락)도 같이 잡았다. 결과적으로 git push 한 번이면 로컬에서 따로 build/push/scp 없이 백엔드+프론트가 전부 배포된다. EC2 보안 그룹에 `8501`(Streamlit) 포트를 여는 것만은 CI가 못 해주는 수동 준비물로 남았다.

## 4. verify가 단기기억(대화 이력)을 못 보던 버그 수정

### 증상

멀티턴 대화에서:
1. "내 이름은 원정재야" → "안녕하세요, 원정재님!" (정상)
2. "내 이름이 뭐라고?" → generate는 이력을 보고 맞게 답하는데, **verify가 매번 "근거 없이 이름을 지어냈다"며 fix_needed=True를 반환** → limit(4)까지 재시도만 반복하다 결국 "이름을 알 수 없습니다"로 답이 뒤집힘

### 원인

`graph.py`의 `generate()`는 `history = state.messages`를 가져와 `[system] + history + new_msgs`로 모델에 넘긴다. 반면 `verify()`는 애초부터 `[SystemMessage(...), HumanMessage(질문+답변)]` 딱 두 개만 넘기고 있었다 — **대화 이력(`state.messages`) 자체를 아예 안 보내고 있었다.** 그래서 verify 입장에서는 문서에도 없고 대화 맥락도 안 보이는 이름이 답변에 등장하니 "근거 없는 사실"로 판단하는 게 코드상 당연한 결과였다. claude 모델이 멍청해서가 아니라 애초에 단기기억을 안 준 것.

### 수정

```python
messages = [
SystemMessage(content=f"""
    ...
    대화 이력에 등장한 정보(예: 사용자가 밝힌 이름 등 단기기억)는 근거로 인정해도 된다 — 문서에 없다는 이유만으로 틀렸다고 판단하지 마라.
    ...
"""),
] + state.messages + [
HumanMessage(f"질문: {state.question}\n\n답변: {state.answer}\n\n이 답변을 검증해줘."),
]
```

`state.messages`(HumanMessage/AIMessage/ToolMessage로 역할이 이미 구분된 리스트)를 그대로 이어붙였다 — 새 메시지 타입으로 감싸지 않고 원래 타입 그대로 넘겨야 모델이 "누가 한 말인지" 헷갈리지 않는다.

### 겸사겸사: 턴이 끝나면 메시지를 정리하도록 추가

`state.messages`를 verify에도 그대로 넘기기 시작하면, 재시도·tool 호출로 쌓인 이번 턴의 잡다한 메시지까지 다음 턴·다음 verify 호출에 계속 누적된다. 기능이 늘어날수록 대화 이력이 무한정 두꺼워지는 걸 막기 위해, `final_answer`에서 이번 턴에 쌓인 메시지는 지우고 **질문 + 최종답변 한 쌍만** 남기도록 정리하는 로직을 추가했다.

```python
# State
turn_start_len: int = 0  # 이번 턴 시작 시점의 messages 길이

# reset_turn — 매 턴 시작 시 기록
"turn_start_len": len(state.messages)

# final_answer — 이번 턴 몫만 골라 정리
this_turn_msgs = state.messages[state.turn_start_len:]
prune = [RemoveMessage(id=m.id) for m in this_turn_msgs]
clean_msgs = [HumanMessage(content=state.question), AIMessage(content=final_text)]
```

구분자(uuid 등)를 메시지 안에 끼워넣고 나중에 스캔해서 찾는 방식도 고려했지만, `state.messages`가 애초에 정수 인덱스로 접근 가능한 리스트이므로 "턴 시작 시점의 길이"만 정수로 기록해두는 쪽이 훨씬 단순하고 안 깨진다. `RemoveMessage(id=...)`로 지우려면 대상 메시지에 `id`가 있어야 하는데, LangGraph의 `add_messages` reducer가 상태에 병합되는 시점에 자동으로 `id`를 채워주므로 별도 처리가 필요 없었다.

### 검증 중 겪은 해프닝

로컬에서 `docker compose --profile frontend up --build -d`로 재빌드했다고 생각했는데도 verify가 여전히 옛날처럼 동작해서 "로직이 진짜 안 고쳐진 건가" 헷갈렸다. `docker exec <container> grep -n "turn_start_len" /app/graph.py`로 컨테이너 안 실제 소스를 직접 까봤더니 아무것도 안 찍혀서 — 이미지가 실제로는 재빌드되지 않고 옛날 그대로였다는 걸 확인했다(원인 미상, 추후 확인 필요). 로그·추측만으로 "코드가 틀렸다"고 단정하지 않고 컨테이너 안을 직접 들여다봐서 "이미지 문제 vs 로직 문제"를 구분한 케이스.

## 5. DEPLOY.md 정리

프론트/CI 변경사항을 반영하며 `DEPLOY.md`도 같이 손봤다:

- 0번(EC2 준비)에 `8501`(Streamlit) 보안 그룹 규칙 추가 — CI가 프론트도 기본으로 배포하니 처음부터 열어두는 게 자연스러워서
- 2.3(최초 파일 전송): `.env`는 git에 없어 CI가 절대 못 옮기니 언제나 수동 scp가 필요한데, 어차피 손대는 김에 `docker-compose.yml`도 같은 명령으로 합쳐서 한 번에 끝내도록 정리(`scp ... docker-compose.yml .env user@host:...`)
- 2.4·2.5(실행·갱신)에 "CI 쓰면 이 과정 전체가 자동"이라는 안내 추가 — 안 그러면 수동 절차가 기본인 것처럼 읽힘
- 2.6(프론트) 이하 번호를 2.7로 밀고, 자동(CI) 흐름을 메인으로 서술한 뒤 "2.6.1 CI 없이 수동 설치", "2.6.2 프론트 없이 설치하려면"을 서브로 뒤에 배치
- 3번(CI/CD 섹션)의 `deploy.yml` 설명을 프론트 빌드+push+scp까지 포함하도록 갱신 — 예전엔 백엔드만 하던 시절 설명이 그대로 남아있었음

## 6. nginx 도입 여부 검토 — 보류

프론트(Streamlit) 앞에 nginx 리버스 프록시를 실습 삼아 세워볼지 논의했다. 결론은 **보류**:

- Streamlit은 위젯 상호작용을 WebSocket으로 처리해서, nginx 기본 `proxy_pass`만으로는 안 되고 `Upgrade`/`Connection: upgrade` 헤더 설정이 추가로 필요함
- RoadMap의 남은 일정(멀티 에이전트 확장, HITL, 장기기억 등)에 인프라 고도화 항목이 없음 — 지금 프론트 요구사항은 애초에 "간이 UI"였고 이미 충족됨
- nginx의 이점(포트 숨기기, TLS, 다중 인스턴스 로드밸런싱)은 도메인+공개 서비스일 때 값어치가 생기는데, 지금은 도메인도 없고 혼자 쓰는 EC2 한 대뿐

재고 조건(도메인 구입, HTTPS 필요, 공개 서비스화)을 `RoadMap.md` 설계 노트와 Obsidian To Do List(🗂️ 언젠가)에 남겨뒀다.

## 7. 아키텍처 개편 — 단일 슈퍼바이저 챗봇 → 표면/능력/데이터 3층

### 7.1 문제의식

멀티 에이전트 전환(6-1) 착수 직전, 설계 전체를 재검토했다. 기존 계획은 "오케스트레이터(Supervisor)가 7~9개 전문 에이전트를 라우팅하는 단일 챗봇"이었는데, 두 가지 의문이 생겼다:

1. 한 챗봇에 모든 기능을 뭉치면 기능 구분이 안 되고 사용자가 헷갈린다
2. 그렇다고 서비스별로 챗봇을 쪼개면? — 관심사 관리 봇, 논문 평가 봇, 추천 봇, QA 봇...

검토 결과 **둘 다 아니었다.** 서비스별 챗봇 분리는 (a) 사용자가 어느 봇에 물을지 스스로 라우팅해야 하고("이 논문 내 관심사에 맞아?"는 세 서비스에 걸침), (b) thread/메모리/프론트엔드가 봇 수만큼 복제된다. 진짜 문제는 "모든 기능을 대화형 챗봇으로 만들려 한 것" 자체였다.

### 7.2 결정 — 기능을 역할별로 다른 층에 놓는다

| 층 | 정의 | 해당 기능 |
|---|---|---|
| **표면** | 사용자가 만나는 화면. 작업 성격에 맞는 UI 형태 | 메인 챗(상시 대화) · 연구 워크플로우(단계형·HITL) · 추천 피드(배치 결과 목록) |
| **능력** | 호출당하는 서브그래프/함수. 챗봇 아님 | 물리 QA(현 그래프) · 논문 분석기 · 문서 작성기 · 가설/설계/운영 · 논문 작성 · 번역 |
| **데이터 서비스** | CRUD + 검색. 저장에 LLM 불필요 | 관심사 저장소 · 논문 요약 VDB · 실험도구 DB · 코퍼스 · 안전 규칙 |

핵심 통찰 세 가지:

- **논문 분석기(②)는 챗봇이 아니라 허브 능력** — 추천 필터(③), 수동 ingest(④), 논문 자체 검토(⑦)가 전부 재사용하는 부품. 사용자와 직접 대화할 일이 없다. 그래서 멀티 에이전트 확장의 최우선 구축 대상으로 승격
- **추천(③)은 챗봇이 아니라 파이프라인** — "관심사별 웹 검색 → ②로 평가 → 랭킹 → 리스트"는 대화가 필요 없는 배치 작업. cron으로 돌리고 결과만 피드로 노출
- **문서 작성기(①⑤ 공용)는 챗봇이 아니라 공유 서브그래프** — "대화 → 템플릿 문서" 변환기를 하나만 만들어 관심사/실험도구 템플릿만 갈아끼움. 중복 검사(유사도 검색 → 신규 대신 기존 편집 제안)와 등록 확인 `interrupt`는 이 안에 한 곳만 구현하면 모든 진입점에 적용. "관심사로 등록할까요?" 제안은 챗 그래프의 턴 종료 후 훅(싼 모델 1회 판정)

결과적으로 그래프는 3개(챗 / 연구 워크플로우 / 추천 파이프라인)로 수렴하고, 오케스트레이터는 "만능 슈퍼바이저"에서 "표면별 얇은 라우터(3~4갈래)"로 축소된다. 사용자 혼란은 챗봇을 쪼개서가 아니라 **작업 성격에 맞는 UI 형태를 매칭해서** 푼다 — 대화는 챗, 추천은 피드, 등록은 폼+어시스트, 연구는 단계형 워크플로우.

### 7.3 이 개편이 기존 계획에 미치는 수정사항

| # | 수정사항 | 이유 |
|---|---|---|
| 1 | 6-1 서브그래프 포장을 **래퍼 함수 노드 방식**으로 (컴파일된 그래프 직접 삽입 X) | 직접 삽입하면 부모와 `messages`(add_messages reducer)를 공유 — 에이전트 내부의 재시도 초안·tool 메시지가 부모 이력에 섞이고, `final_answer`의 `RemoveMessage` 정리가 부모까지 건드림. 래퍼에서 `invoke()` 입출력을 명시 매핑하면 State 스키마 충돌 자체가 없음 |
| 2 | checkpointer를 부모 컴파일로, `reset_turn`도 부모 소속으로 | 서브그래프는 부모 checkpointer를 상속. 턴 경계도 부모 개념 — 한 사용자 턴에 같은 능력이 두 번 호출될 수 있는데 그때마다 reset되면 안 됨 |
| 3 | 스트리밍 API(SSE)를 워크플로우 구축 **전에** 도입 | 동기 `POST /query`로는 "실험 운영이 비동기로 진행상황 전달"을 실을 채널이 없고, 긴 워크플로우는 프론트 `timeout=120`도 뚫음. 나중에 넣으면 모든 능력의 진행상황 배선을 재작업 |
| 4 | SqliteSaver를 HITL **앞으로** (기존 로드맵은 HITL 08-03 → SqliteSaver 08-11) | interrupt로 멈춘 그래프는 checkpointer에서 재개됨 — MemorySaver면 승인 대기 중 서버 재시작 시 대기 상태 증발. resume 엔드포인트 API 설계도 함께 필요 |
| 5 | comment 채널 분리 | 현재 comment는 사용자용 부가정보 + 디버그 트레이스(매 generate/verify 누적) 혼재. 능력이 늘면 폭발 — 트레이스는 LangSmith 몫으로 |
| 6 | 후속 질문 재작성(기존 08-10 별도 항목)을 메인 챗 라우터에 통합 | 라우팅 결정과 "능력에 넘길 정제된 task"를 structured output 한 번에 — 별도 LLM 호출 불필요. `retrieve`가 `state.question`을 그대로 검색어로 쓰는 문제도 함께 해소 |
| 7 | `disabled_models`를 부모 State 공유로 | gemini 쿼터 소진을 능력마다 각자 재발견할 필요 없음 |
| 8 | 라우팅 평가셋(10~20문항) 신설 | 라우터가 생기면 "어느 능력으로 보냈어야 하는가" 자체가 새 실패 지점 — eval.json(QA 품질)과 별개 축 |
| 9 | 실험도구 DB는 구조화 레코드 우선 | 장비 spec은 유사도 검색이 아니라 정확 조회가 필요 — VDB는 선택적 보조 |
| 10 | `docs/architecture.png` 재작성 | 3층 구조 반영해 새로 그려 교체 완료 (matplotlib 스크립트 생성) — README가 새 이미지를 참조 |

반영 위치: README §목표 아키텍처(전면 교체), RoadMap §예정(순서 재편)·§설계 노트(결정 기록), Obsidian To Do List(6-x 항목 교체). **6-1(현 그래프 포장)은 이 구조에서도 그대로 첫 단계라 기존 작업 방향은 유효하다** — 방식만 래퍼 노드로 확정됐고, 다음 순서가 "오케스트레이터"에서 "논문 분석기"로 바뀌었다.

## 8. 6-1 실행 — orchestrator.py 분리 + effort 프로필 + 6-2 스트리밍/comment 정리

### 8.1 6-1: graph.py → orchestrator.py 분리 (래퍼 함수 노드)

§7.3에서 정한 방식(래퍼 함수 노드, State 비공유)대로 실행했다. `graph.py`에서 `MemorySaver`/`reset_turn`을 통째로 뺐다 — orchestrator가 매 턴 능력을 fresh하게 부르므로(`physics_qa_app.invoke()`, 지금은 `.stream()`으로 바뀜 — 8.3 참고), `reset_turn`이 하던 일(임시 필드 초기화)은 Pydantic 기본값이 이미 대신해준다. 당초 "reset_turn을 부모로 옮긴다"는 계획보다 더 단순해졌다 — 아예 필요가 없어졌다.

`orchestrator.py` 신설:
- `ParentState`(question/answer/comment/model/effort/tokens_used/disabled_models/messages) — 능력 내부 전용 필드(try_count/tool_rounds/disabled_tools 등)는 안 들어감
- `physics_qa_node` 래퍼: 능력을 호출하고, 반환된 messages 중 "이번 호출에서 새로 생긴 것"만 슬라이싱해 부모에 전달(옛 메시지까지 매번 교체 시도하는 낭비 방지, `add_messages`는 id 병합이라 중복 append는 원래 안 됨)

`main.py`가 `graph.app` 대신 `orchestrator.app`을 부르도록 전환, mock 모델로 멀티턴 스모크 테스트(메시지 중복 없이 정상 누적) 검증 완료.

### 8.2 effort 프로필 — top_k/limit을 사용자 노출 다이얼로

top_k/limit 자체는 "능력 내부 다이얼이라 부모 State에 안 넣는다"는 §7.3의 판단을 유지하되, Claude의 reasoning effort와 같은 패턴으로 그 위에 `low/medium/high` 선택지만 노출하기로 했다. 숫자 매핑(`EFFORT_PROFILES = {"low": {"top_k":2,"limit":2}, "medium": {...}, "high": {...}}`)은 능력마다 다를 수 있는 내부 지식이라 `graph.py` 안에 두고, `ParentState`/`main.py`/프론트는 문자열 이름만 그대로 통과시킨다(`model` 필드와 같은 위치·역할). `State`의 `top_k`/`limit` 기본값을 -1(미지정 센티널)로 바꾸고 `model_validator(mode="after")`로 -1일 때만 프로필값을 채우게 해서, 재검색 중 이미 갱신된 값은 안 건드리게 했다. 죽어있던 프론트 `top_k` 슬라이더를 `effort` 선택박스로 교체.

### 8.3 6-2: 스트리밍 API + comment/트레이스 채널 분리

당초 계획(§예정)은 `stream_mode="updates"`였는데, 구조상 걸리는 게 하나 있었다: orchestrator 그래프엔 노드가 `physics_qa` 하나뿐이라(래퍼 함수 노드 패턴), 부모 그래프 자체를 `stream_mode`로 스트리밍해도 능력 내부(retrieve/generate/verify)의 진행 상황은 안 보인다 — 래퍼가 `.invoke()`로 결과를 한 번에 받아오기 때문. 그래서 대신:

- `physics_qa_node` 내부에서 능력을 `physics_qa_app.stream(stream_mode="values")`로 순회 — "values"는 매 노드가 끝날 때마다 그 시점까지의 전체 State 스냅샷을 주므로, 마지막 스냅샷은 기존 `.invoke()` 반환값과 완전히 동일(정확성 그대로 유지)
- 매 스냅샷마다 `get_stream_writer()`로 부모 스트림에 진행 상황을 흘려보냄 — orchestrator가 `stream_mode="custom"`으로 스트리밍될 때만 실제로 효과가 있는 "쓰기 채널"이라, 기존 동기 `invoke()` 호출(테스트 등)엔 아무 영향 없음
- `main.py`의 `/query`가 `async def`로 바뀌고 `app_graph.astream(..., stream_mode="custom")`을 그대로 SSE(`data: ...\n\n`)로 흘려보냄

진행 상황을 실제로 스트리밍해보면서 새 문제가 드러났다: **comment 필드가 두 역할을 겸하고 있었다** — (1) 각 노드가 이어붙이는 내부 디버그 로그, (2) `final_answer`가 최종적으로 사용자에게 보여줄 코멘트. `try_count==1`(첫 시도 통과, 제일 흔한 경우)엔 `final_answer`가 `state.comment`를 그대로 통과시키는데, 그 시점 `state.comment`엔 이미 트레이스 전체가 쌓여있어서 "사용자용 코멘트"라는 이름으로 사실상 디버그 로그가 나가고 있었다(프론트의 💬 캡션과 "판단 과정 보기" expander 내용이 겹치는 걸로 발견). §7.3 항목 5(comment 채널 분리)가 원래 계획에 있었는데 이 타이밍에 실제로 필요해진 것.

수정: `State`에 `trace`(내부 디버그 로그, 계속 누적) 필드를 신설하고, 각 노드가 쌓던 로그를 `comment` → `trace`로 옮겼다. `comment`는 `verify`가 structured output으로 이미 뽑고 있던 `answer.comment`("사용자가 알아야 할 주의점")를 그대로 담도록 정리 — reducer 없이 매번 덮어쓰기라 "가장 최근 verify의 의견"만 남는다. 검증 자체가 생략되는 예외 분기에도 트레이스 뒤에 숨기지 않고 `comment`에 "검증을 수행하지 못해 결과를 확인 없이 반환합니다"를 명시적으로 채웠다.

프론트(`frontend/app.py`)는 진행 중엔 `trace`를 실시간 로그로 보여주다가, `final: true` 이벤트가 오면 답변(`answer`) + 클린한 `comment`(💬)로 전환하고, 전체 `trace`는 "판단 과정 보기" expander로 접어서 남긴다.

## 업데이트

- 2026-07-23: CI 테스트 게이트(test/deploy job 분리 + 이미지 정리) 반영, Streamlit 프론트엔드 추가(별도 서브프로젝트·별도 이미지) + docker-compose 통합(profiles로 선택 설치), verify가 대화 이력을 못 보던 버그 수정 + 턴 종료 시 메시지 정리(`RemoveMessage`) 추가.
- 2026-07-24: `turn_start_len` 누락으로 인한 CI 테스트 실패 수정(게이트 정상 작동 확인). CI/CD가 프론트까지 항상 같이 배포하도록 `deploy.yml` 확장(프론트 이미지 빌드+push, `docker-compose.yml` 자동 scp 전송) + 태그 오타 수정. `DEPLOY.md`를 이 변경사항에 맞게 정리. nginx 도입은 보류하고 재고 조건을 로드맵에 기록.
- 2026-07-24 (2): **아키텍처 개편** — 단일 슈퍼바이저 챗봇 → 표면/능력/데이터 3층 구조 (§7). README 목표 아키텍처 전면 교체, RoadMap 예정 순서 재편(논문 분석기 최우선, 스트리밍·SqliteSaver 전진 배치), To Do List 동기화.
- 2026-07-24 (4): **설계 확장 — 표면 4개 체제**: 라이브러리 표면 신설(관심사·논문·실험도구·지식 노트 관리 통합 — 논문 등록의 주 경로), 피드 재정의(관심사 무관 hype 소식 cron 크롤링 + 키워드 태깅 + 관심사 일치 색 강조·상단 정렬), 추천 검색(③)은 관심사 트리거 온디맨드로 전환, 논문 카탈로그(DOI 기본 키, status로 등록 시 추천에서 자동 하차), 지식 노트(`user_note` 신뢰도 구분). 외부 논문 API(Crossref·Unpaywall·OpenAlex)는 최종 단계 어댑터로 후순위 명시. 프론트 스택 재검토(Streamlit 한계) 노트. architecture.png 재갱신.
- 2026-07-27: **6-1 실행** — orchestrator.py 분리(래퍼 함수 노드, checkpointer·reset_turn 부모 소속 → reset_turn 자체가 불필요해져 삭제), mock 스모크 테스트 검증. **effort 프로필** 도입(low/medium/high, Claude reasoning effort 패턴 — 숫자 매핑은 능력 내부에 캡슐화). **6-2 실행** — 스트리밍 API(SSE): 당초 계획한 `stream_mode="updates"` 대신 래퍼 함수 노드 패턴 특성상 `get_stream_writer()` + `stream_mode="custom"`으로 능력 내부 진행상황을 직접 흘려보내는 방식으로 조정. §7.3 항목 5(comment 채널 분리) 실행 — `trace`(내부 디버그 로그) 신설, `comment`는 verify의 구조화 출력만 담도록 정리(§8).
- 2026-07-27 (2): **arxiv API 이슈 해결(6-3 선행)** — `arxiv_api.py` 신설, export.arxiv.org 공식 API 직접 호출로 구조화된 서지정보(제목·저자·연도·arxiv id) 확보. `tool.py`의 DDG `site:arxiv.org` 우회를 `search_arxiv` tool로 교체. 진단 중 curl 대조 테스트로 코드 문제가 아니라 arxiv 자체 rate limit(429/503)임을 확인 → 3초 스로틀링 + `Retry-After` 존중 재시도 추가. 파싱 로직을 네트워크와 분리해 `tests/test_arxiv_api.py`로 톨게이트 테스트화(§9).
- 2026-07-24 (3): **참고문헌 추천기 설계 추가** — ③과 검색·평가 내부를 공유하는 온디맨드 능력. 참고문헌은 연구 워크플로우가 끌고 다니는 누적 산출물(가설 단계부터 각 단계가 append, 서지+인용 이유+단계 기록 → ⑦이 소비, 목록 밖 인용은 환각 신호). QA(④)는 기본 retrieve 메타데이터 "참고" 부착(추가 호출 0) + 온디맨드 풀 호출. 전제: ② 요약 VDB 메타데이터에 서지정보 포함. README 능력 표·설계 포인트, RoadMap, To Do List 반영.
- 2026-07-27 (3): **tool 라운드 예산 낭비 버그 수정** — 실전 arxiv 서킷 브레이커 케이스에서, 이미 disabled된 tool 재요청/한도 초과 거부처럼 실행을 시도조차 안 한 라운드까지 `tool_rounds`가 소모되어 fallback tool이 시도될 라운드가 안 남던 문제 발견. `run_tools()`에 `attempted` 플래그 추가해 실제 실행 시도가 있을 때만 라운드 소모하도록 수정(§10). 전역 라운드 캡은 tool별 서킷 브레이커와 목적이 달라(라운드-로빈 실패 패턴 방지) 유지.

## 9. arxiv API 이슈 해결 (6-3 선행 조건)

`tool.py`에 `#ArxivQueryRun(),  #arxiv.org 서버 자체 이슈 (2025-11 이후), langchain_community도 구버전 API 요구`라는 주석과 함께 막혀있던 게 있었다 — 그 우회책으로 DuckDuckGo에 `site:arxiv.org`를 붙여 검색해왔는데, 검색 스니펫만 줄 뿐 논문 분석기(6-3)가 필요로 하는 구조화된 서지정보(제목·저자·연도·arxiv id)는 못 준다. 6-3 착수 전에 반드시 풀어야 하는 선행 조건이었다.

### 9.1 방향 결정

세 가지 옵션을 검토했다 — ① arxiv 공식 API를 직접 호출(Atom XML 파싱), ② `arxiv` PyPI 패키지(전용 클라이언트) 사용, ③ 지금 방식(DDG 검색) 유지하고 LLM이 스니펫에서 메타데이터를 추출. ③은 구조화 정확도가 근본적으로 불안정(환각 위험)해서 제외, ①·② 중 새 의존성이 필요 없고 표준 라이브러리(`xml`)+이미 있는 `requests`만으로 되는 ①을 선택했다.

`arxiv_api.py` 신설 — `export.arxiv.org/api/query`(Atom XML)를 직접 호출·파싱해 `title/authors/year/arxiv_id/summary/pdf_url` 구조화 dict를 반환하는 `arxiv_search()`. `tool.py`는 이걸 감싼 `search_arxiv` tool로 기존 DDG 우회를 교체(물리 QA의 tool-calling 루프에 편입), 원본 dict 반환 함수는 6-3 논문 분석기가 그대로 재사용할 수 있게 남겨뒀다.

### 9.2 실행하며 겪은 문제 — rate limit 진단

로컬에서 처음 돌렸을 때 20초 `ReadTimeout`이 났다. 코드 문제인지 네트워크(방화벽·VPN) 문제인지 구분하기 위해 `curl -v`로 같은 엔드포인트를 직접 찔러봤더니 — curl은 빠르게 `429 Too Many Requests` ("Rate exceeded")를 받았다. 즉 접속 자체는 정상이고, **arxiv 서버가 실제로 요청을 제한**하고 있었던 것 — 타임아웃은 그 제한 상태에서 응답이 지연된 것으로 보인다. 이후 짧은 시간에 curl·python으로 반복 테스트하다 `503`(arxiv 문서상 "서버 과부하, `Retry-After` 헤더 존중" 응답)까지 겪었다. curl과 python 양쪽으로 대조 테스트해서 "코드가 틀렸다"와 "외부 서비스가 제한 중이다"를 구분한 사례 — README_12 §4의 "재빌드 안 됐는데 로직 버그로 오인할 뻔한 것"과 같은 종류의 교훈이다.

대응:
- 요청 간 3초 스로틀링(`_throttle()`, arxiv 공식 가이드라인)
- 429/503에 대해 `Retry-After` 헤더를 존중하며 최대 2회 자동 재시도
- 테스트 중 반복 요청으로 IP가 더 강하게 제한된 구간에선 재시도도 무의미해서, 그냥 대기 후 재확인 — 이후 정상 동작 확인(논문 3건 제목/저자/연도/id/요약 정상 반환)

### 9.3 겸사겸사 — 파싱 로직을 네트워크와 분리해 테스트 가능하게

`_parse_atom_response(xml_text)`를 네트워크 호출(`arxiv_search`)에서 분리했다 — 그래야 실제 arxiv API를 두드리지 않고도(=rate limit 걱정 없이) pytest로 파싱 로직을 검증할 수 있다. arxiv 공식 문서 예시 형식 그대로 만든 샘플 Atom XML로 `tests/test_arxiv_api.py`에 3개 테스트(정상 파싱/summary 공백 정규화/빈 피드) 추가 — 기존 톨게이트 테스트 철학(외부 의존성 없이 1~2초 안에 끝남)을 그대로 따름.

## 10. tool 라운드 예산 낭비 버그 수정

### 증상

실전 대화("최근 얽힘 관련 arxiv 논문 찾아줘")에서 `search_arxiv`가 계속 `ReadTimeout`을 내는 상황을 재현했는데, 최종적으로 `duckduckgo_search`로 fallback했어야 할 결과가 "arXiv 도구가 작동하지 않아 찾을 수 없다"는 답으로 끝났다. verify는 이걸 "제약된 상황에서 정직한 답"으로 통과시켰지만, SSE 트레이스를 전부 까보니 `duckduckgo_search`는 **한 번도 실제로 실행되지 못했다** — `[한도 초과]`로 거부된 것.

### 원인

라운드별 순서를 재구성하면:

1. 1라운드: `search_arxiv` 요청 → `ReadTimeout` (실패 1회차) → `tool_rounds` 1
2. 2라운드: `search_arxiv` 재요청 → `ReadTimeout` (실패 2회차) → 서킷 브레이커 발동, `disabled_tools`에 추가 → `tool_rounds` 2
3. 3라운드: LLM이 아직 disabled된 걸 모르고 `search_arxiv`를 또 요청 → `run_tools()`가 `[사용 불가]`로 즉시 거부(실행 자체를 안 함) → 그런데도 `tool_rounds`가 3으로 올라감
4. LLM이 `duckduckgo_search`로 전환해도, 이미 `tool_rounds >= MAX_TOOL_ROUNDS(3)`라 `[한도 초과]`로 거부 — 실행 기회 자체가 없음

즉 `run_tools()`가 `tool_rounds`를 "실제로 tool을 실행해봤는지"와 무관하게 **호출 1번당 무조건 +1**로 세고 있었다. `[한도 초과]`/`[사용 불가]`처럼 실행을 시도조차 안 한 조기 거부까지 라운드로 소모되면서, 정작 fallback tool이 시도될 라운드가 남지 않았다.

전역 라운드 캡 자체를 없애고 "tool별 연속 실패 횟수"만으로 대체하는 방안도 검토했지만 기각했다 — 서킷 브레이커는 이미 tool별로 따로 돌고 있고(`tool_failures`), 전역 캡은 그것과 다른 문제(여러 tool을 번갈아 실패하는 라운드-로빈 패턴에서 tool 호출이 무한정 늘어나는 것)를 막는 별개의 안전장치라, 없애면 이 시나리오의 무한루프 방지가 안 된다.

### 수정

`run_tools()`에 `attempted` 플래그를 추가해, 실제로 `tool_map[name].invoke()`를 시도한 tool_call이 이번 호출에 하나라도 있었을 때만 `tool_rounds`를 올리도록 바꿨다.

```python
attempted = False
for tc in last.tool_calls:
    ...
    if rounds >= MAX_TOOL_ROUNDS:
        ...; continue  # 실행 안 함 → attempted 그대로
    if name not in tool_map or name in disabled:
        ...; continue  # 실행 안 함 → attempted 그대로
    attempted = True
    try:
        result = str(tool_map[name].invoke(tc["args"]))[:4000]
    ...

return {..., "tool_rounds": rounds + 1 if attempted else rounds, ...}
```

이렇게 하면 위 3라운드의 거부는 예산을 안 깎고, LLM이 다음에 `duckduckgo_search`로 전환했을 때 실제로 실행될 라운드가 남는다.

## 회고

verify에 대화 이력을 안 넘기고 있었다는 게 코드를 짜고 나서야 실제 멀티턴 대화로 써보다가 드러났다 — `route_by_fix`/`reset_turn`처럼 순수 함수 단위 pytest로는 애초에 잡을 수 없는 종류의 버그였다(여러 노드에 걸친 "이 정보가 이 노드까지 전달되는가" 통합 이슈). 톨게이트 테스트가 커버하는 범위와, 실제로 대화해봐야 드러나는 범위가 다르다는 걸 다시 확인했다. 재빌드가 안 됐는데 로직 버그로 오인할 뻔한 것도 비슷한 교훈 — 로그만 보고 판단하지 말고 컨테이너 안을 직접 까봐야 확실해진다.

tool 라운드 예산 버그도 같은 계열이다 — `run_tools()`/`generate()` 각각은 단위 테스트로 봐도 이상이 없어 보였는데(서킷 브레이커도 정상 발동, active_tools 필터링도 정상), 실제 실패가 여러 라운드에 걸쳐 누적되는 실전 시나리오를 SSE 트레이스로 라운드 단위까지 재구성하고 나서야 "거부도 라운드를 먹는다"는 상호작용이 드러났다. 개별 함수가 맞아도 여러 라운드/여러 노드에 걸친 예산 계산은 따로 검증해야 한다는 교훈.
