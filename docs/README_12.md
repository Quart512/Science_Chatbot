# README_12 — 배포 전 테스트 게이트 · 프론트엔드(Streamlit) · verify 단기기억 버그 수정

## 1. 배포 전 테스트 게이트 (CI)

(README_11에서 다룬 내용과 중복이지만 이번 세션 변경 이력에 포함되어 다시 짧게 적는다.)

`.github/workflows/deploy.yml`을 `test` / `deploy` 두 job으로 분리했다. `test` job이 `uv sync` + `uv run pytest`(4개 톨게이트 테스트)를 돌리고, `deploy` job은 `needs: test`로 걸려 있어 테스트 실패 시 이미지 빌드·EC2 배포 자체가 시작되지 않는다. EC2 배포 스크립트에는 `docker image prune -f`도 추가해 배포 때마다 쌓이는 옛 이미지를 자동 정리하게 했다.

## 2. 프론트엔드(Streamlit) 도입

`/docs`(Swagger UI)로만 API를 두드려볼 수 있던 걸 대체할 최소 채팅 UI를 Streamlit으로 붙였다(`frontend/app.py`). 백엔드와 완전히 분리된 별도 서브프로젝트(`frontend/pyproject.toml`·`uv.lock`·`Dockerfile`)로 만들었다 — 백엔드는 이미 8.77GB → 2.04GB로 줄여둔 이미지라, Streamlit의 무거운 의존성 트리를 얹으면 그 작업이 무의미해지기 때문(`llama-server`를 별도 이미지로 분리했던 것과 같은 이유). `thread_id`를 세션당 한 번만 발급해 유지하고, 요청 페이로드는 `main.py`의 `Query` 스키마와 맞춰 백엔드 단기기억(`MemorySaver`)이 그대로 이어지게 했다.

## 3. 프론트 컨테이너 분리 + docker-compose 통합

`docker-compose.yml`에 `frontend` 서비스를 `profiles: ["frontend"]`로 추가했다 — `llama-server`와 같은 패턴으로, API만으로도 충분하니 기본 `up`엔 안 뜨고 `--profile frontend up`으로 선택 설치. `depends_on`은 한때 `condition: service_healthy` + healthcheck(10초마다 내부에서 `/docs` GET)까지 붙여봤지만, 유휴 상태에서도 로그가 계속 쌓이는 게 거슬리고 개인 프로젝트 규모에 과한 엄밀함이라 판단해 순서만 보장하는 평범한 `depends_on`으로 되돌렸다. 이미지 크기는 프론트 760MB(컨텐츠 173MB) vs 백엔드 2.04GB(컨텐츠 418MB)로, 분리 효과(무거운 langchain 계열 의존성 미포함)를 확인했다.

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

## 업데이트

- 2026-07-23: CI 테스트 게이트(test/deploy job 분리 + 이미지 정리) 반영, Streamlit 프론트엔드 추가(별도 서브프로젝트·별도 이미지) + docker-compose 통합(profiles로 선택 설치), verify가 대화 이력을 못 보던 버그 수정 + 턴 종료 시 메시지 정리(`RemoveMessage`) 추가.

## 회고

verify에 대화 이력을 안 넘기고 있었다는 게 코드를 짜고 나서야 실제 멀티턴 대화로 써보다가 드러났다 — `route_by_fix`/`reset_turn`처럼 순수 함수 단위 pytest로는 애초에 잡을 수 없는 종류의 버그였다(여러 노드에 걸친 "이 정보가 이 노드까지 전달되는가" 통합 이슈). 톨게이트 테스트가 커버하는 범위와, 실제로 대화해봐야 드러나는 범위가 다르다는 걸 다시 확인했다. 재빌드가 안 됐는데 로직 버그로 오인할 뻔한 것도 비슷한 교훈 — 로그만 보고 판단하지 말고 컨테이너 안을 직접 까봐야 확실해진다.
