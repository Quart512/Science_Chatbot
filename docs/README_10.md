# 10주차 과제 — 유닉스 프로세스 분석 + WireShark 패킷 캡처

> 과제 원문: (1) 개인 프로젝트 서버 프로세스를 실행한 뒤 유닉스 명령어로 프로세스·스레드·메모리 상태를 조회·분석 (2) WireShark로 서버의 HTTP/HTTPS 통신 캡처

대상 서버: `Science_Chatbot` — FastAPI (`main.py`, `uv run fastapi dev main.py`로 실행, `/query` 엔드포인트)

---

## 1. 유닉스 프로세스·스레드·메모리 상태 조회

### 1.1 서버 프로세스 확인 (`ps -ef`)

```bash
ps -ef | grep main.py
```

```
  501 63322 61394   0  9:08AM ttys003    0:00.00 grep main.py
  501 61217 46087   0  8:52AM ttys005    0:00.04 uv run fastapi dev main.py
  501 61218 61217   0  8:52AM ttys005    0:05.38 /Users/jimmywon/Documents/Science_Chatbot/.venv/bin/python /Users/jimmywon/Documents/Science_Chatbot/.venv/bin/fastapi dev main.py

```

| PID | PPID | 역할 |
|---|---|---|
| 61217 | 46087 | `uv run fastapi dev main.py` (uv 래퍼) |
| 61218 | 61217 | 실제 파이썬 서버 프로세스 (uvicorn worker) |

두 프로세스가 부모-자식 관계로 뜨는 이유: `uv run`은 `uv` 자체가 먼저 실행되고, 그 안에서 실제 파이썬 프로세스를 자식으로 fork/exec하기 때문. 스레드·메모리 조회는 아래부터 자식 프로세스(PID)를 대상으로 진행.

### 1.2 프로세스·스레드·메모리 상태 (`top -pid <PID>`)

```bash
top -pid <실제 PID>
```

```
Processes: 625 total, 5 running, 1 stuck, 619 sleeping, 4524 threads                                                                09:13:47
Load Avg: 2.97, 3.19, 3.78  CPU usage: 10.34% user, 5.7% sys, 84.57% idle  SharedLibs: 444M resident, 86M data, 73M linkedit.
MemRegions: 0 total, 0B resident, 0B private, 5532M shared. PhysMem: 23G used (3226M wired, 6668M compressor), 450M unused.
VM: 309T vsize, 6144M framework vsize, 806606(8) swapins, 1881577(0) swapouts. Networks: packets: 28440696/29G in, 7546468/3926M out.
Disks: 19268471/538G read, 12601731/247G written.

PID    COMMAND      %CPU TIME     #TH  #WQ  #POR MEM    PURG CMPRS PGRP  PPID  STATE    BOOSTS    %CPU_ME %CPU_OTHRS UID  FAULTS  COW
61218  python3.14   0.0  00:05.55 15   2    83   3909M  0B   866M  61217 61217 sleeping *0[1]     0.00000 0.00000    501  132109  140539
```

확인할 항목:

| 항목 | 값 | 의미 |
|---|---|---|
| `#TH` | 15 | 스레드 개수 |
| `%CPU` | 0.0  | CPU 점유율 |
| `MEM` | 3909M | 실제 메모리 사용량 |
| `STATE` | sleeping | 프로세스 상태(running/sleeping 등) |

분석 메모: 요청이 없는 유휴 상태에서 `#TH=15`, `STATE=sleeping`, `%CPU=0.0` — uvicorn/FastAPI는 단일 비동기 이벤트 루프로 동작하므로, 아무 요청도 안 들어온 상태에선 이벤트 루프가 할 일이 없어 잠들어(sleeping) 있고 CPU도 거의 안 쓰는 게 정상. 스레드 수 15는 이벤트 루프 자체가 쓰는 스레드 외에 파이썬 인터프리터·라이브러리(임베딩 모델, 벡터스토어 클라이언트 등)가 초기화 시점에 미리 띄워둔 백그라운드 스레드들로 추정 — 1.4에서 요청이 들어오자 34까지 늘어난 것과 비교하면, 이 15는 "대기 중 기본 스레드", 나머지 증가분은 "요청 처리에 쓰인 스레드"로 구분해볼 수 있음.

### 1.3 열려 있는 포트·소켓 (`lsof -i`)

```bash
lsof -i :8000
```

```
COMMAND     PID     USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
Code\x20H  6029 jimmywon   28u  IPv4 0xf753c9db158b8ea3      0t0  TCP localhost:54371->localhost:irdmi (CLOSED)
python3.1 61218 jimmywon   20u  IPv4 0x539522787ab18786      0t0  TCP localhost:irdmi (LISTEN)
python3.1 63018 jimmywon   20u  IPv4 0x539522787ab18786      0t0  TCP localhost:irdmi (LISTEN)
```

확인할 것: 어떤 PID가 8000번 포트를 LISTEN 상태로 점유하고 있는지 — 1.1에서 찾은 PID와 일치하는지 대조.

### 1.4 요청 처리 중 자원 변화 관찰

`top -pid <PID>` 창을 띄워둔 채로 다른 터미널에서 요청 발생:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "질문 내용"}'
```

| 시점 | %CPU | MEM | #TH |
|---|---|---|---|
| 요청 전 | 0.0  | 3909M | 17 |
| 요청 처리 중 | 0.3  | 4049M | 34 |
| 요청 완료 후 | 0.2 | 4049M | 31 |

분석 메모: 요청이 들어오는 순간 스레드 수가 17→34로 거의 두 배 늘었다가, 완료 후 31로 일부만 줄어듦 — 완전히 17로 복귀하지 않는 건 요청 처리에 쓰인 스레드 풀(예: DB 커넥션, 임베딩/LLM 호출 등 blocking I/O를 async 이벤트 루프 밖 스레드로 위임하는 부분)이 바로 반납되지 않고 유휴 상태로 남아있기 때문으로 추정. MEM도 3909M→4049M로 늘어난 뒤 완료 후에도 안 줄어듦 — 파이썬 GC가 즉시 메모리를 OS에 반환하지 않고 프로세스가 들고 있는 경우가 많아, 짧은 관찰 구간에서는 감소가 안 보일 수 있음. %CPU는 순간 스파이크라 요청 처리 타이밍에 top이 정확히 샘플링됐는지에 따라 값이 낮게 잡혔을 수 있음(0.3%는 상대적으로 가벼운 요청이었거나 top 갱신 주기와 어긋났을 가능성).

### 1.5 프로세스 종료 동작 (`kill`)

```bash
kill <PID>       # SIGTERM — 정상 종료 요청
# 반응 없으면
kill -9 <PID>    # SIGKILL — 강제 종료
```

```
(science-chatbot) jimmywon@jjui-MacBookPro Science_Chatbot % ps -ef | grep main.py

  501 66405 61394   0  9:29AM ttys003    0:00.00 grep main.py
  501 66374 46087   0  9:29AM ttys005    0:00.03 uv run fastapi dev main.py
  501 66375 66374   0  9:29AM ttys005    0:02.90 /Users/jimmywon/Documents/Science_Chatbot/.venv/bin/python /Users/jimmywon/Documents/Science_Chatbot/.venv/bin/fastapi dev main.py
(science-chatbot) jimmywon@jjui-MacBookPro Science_Chatbot % kill 66375           

(science-chatbot) jimmywon@jjui-MacBookPro Science_Chatbot % ps -ef | grep main.py

  501 66697 61394   0  9:30AM ttys003    0:00.00 grep main.py
  ```

분석 메모: `kill 66375`(SIGTERM, 정상 종료 요청)만으로 `ps -ef | grep main.py`에 아무 프로세스도 안 남음 — `kill -9`(강제 종료) 없이도 정상 종료됨. 자식(uvicorn 워커) 프로세스를 죽였는데 부모(`uv run fastapi dev`, PID 66374)까지 같이 사라진 걸 보면, 부모가 자식의 종료를 감지하고 자신도 함께 종료하도록 구성돼 있는 것으로 보임(리로더가 워커 없이는 의미가 없으니 같이 죽는 게 정상적인 설계). 참고로 앞서(1.4 이전) 다른 인스턴스에서는 워커를 죽였더니 새 PID로 자동 재시작되는 걸 관찰한 적이 있는데, 그건 코드 변경으로 인한 재시작(watchfiles reload)과 겹친 상황이었을 가능성이 높음 — 순수 종료 테스트에서는 이번처럼 깔끔하게 종료되는 게 기본 동작.

---

## 2. WireShark HTTP/HTTPS 통신 캡처

### 2.1 캡처 환경

- 클라이언트: 로컬 (같은 머신에서 curl로 요청)
- 캡처 인터페이스: `Loopback: lo0`
- 필터: `tcp.port == 8000` (디스플레이 필터 문법 — 캡처 필터의 `port 8000`과는 다름)

### 2.2 캡처 절차

1. WireShark에서 위 인터페이스 선택 후 캡처 시작
2. `curl` 또는 클라이언트에서 `/query`로 요청 전송
3. 캡처 중지 후 `port 8000` 필터 적용

### 2.3 캡처 결과

필터: `tcp.port == 8000`

```
No.  Time      Source              Destination         Protocol  Info
43   133.298   ::1                 ::1                 TCP       54732 → 8000 [SYN] ...
44   133.298   ::1                 ::1                 TCP       8000 → 54732 [RST, ACK] ...   ← IPv6는 거절(포트 안 열림)
45   133.298   127.0.0.1           127.0.0.1           TCP       54733 → 8000 [SYN] ...
46   133.298   127.0.0.1           127.0.0.1           TCP       8000 → 54733 [SYN, ACK] ...
47   133.298   127.0.0.1           127.0.0.1           TCP       54733 → 8000 [ACK] ...
48   133.298   127.0.0.1           127.0.0.1           TCP       [TCP Window Update] ...
49   133.298   127.0.0.1           127.0.0.1           HTTP/JSON POST /query HTTP/1.1, JSON(application/json)
50   133.298   127.0.0.1           127.0.0.1           TCP       [ACK]
55   143.539   127.0.0.1           127.0.0.1           HTTP/JSON HTTP/1.1 200 OK, JSON(application/json)   ← 49→55 사이 약 10초 소요
56~60                                                  TCP       ACK / FIN,ACK / ACK / FIN,ACK / ACK  ← 4-way 종료
```

### 2.4 분석

| 확인 항목 | 관찰 내용 |
|---|---|
| TCP 3-way handshake (SYN → SYN/ACK → ACK) | 패킷 45→46→47에서 정상적으로 확인됨. 그 직전 43/44는 흥미로운 부산물 — `curl`이 `localhost`를 resolve하면서 IPv6(`::1`)로 먼저 접속을 시도했으나 uvicorn이 IPv4(`127.0.0.1`)에만 바인딩돼 있어 곧바로 `RST, ACK`로 거절당함. 이후 IPv4로 재시도해 성공(happy-eyeballs 방식 fallback) |
| HTTP 요청 패킷 (메서드·헤더·body) | 패킷 49 = `POST /query HTTP/1.1`, `Content-Type: application/json`, body `{"prompt": "..."}` — curl로 보낸 그대로 일치 |
| HTTP 응답 패킷 (상태 코드·body) | 패킷 55 = `HTTP/1.1 200 OK`, `server: uvicorn`, `content-type: application/json`, body `{"answer": ..., "comment": ...}` — main.py의 반환 스키마와 일치 |
| Follow → TCP Stream 결과 | 요청·응답 헤더와 JSON body 전체가 평문 그대로 노출됨 — 요청의 `prompt` 값, 응답의 `answer`/`comment`(내부 verify 로그, `generated_by` 모델명 등)까지 전부 읽을 수 있음 |
| (HTTPS인 경우) TLS handshake 여부 | 해당 없음 — 이 서버는 HTTP(평문)만 서빙하므로 TLS handshake 자체가 없음 |

분석 메모: 패킷 49(요청)와 55(응답) 사이에 약 10초(133.298→143.539) 간격이 있는데, 이건 네트워크 지연이 아니라 서버가 그 사이 LLM 호출(generate→verify 등 그래프 실행)을 처리하느라 걸린 시간 — TCP 연결은 그동안 계속 열린 채 대기(ACK만 오가고 새 SYN 없음)했다는 게 패킷으로 확인됨. 가장 중요한 확인: HTTP는 암호화가 없는 프로토콜이라 body에 담긴 JSON(질문 프롬프트는 물론, 응답 안의 `comment`에 있던 내부 디버그 정보까지)이 캡처 시점에 전부 평문으로 노출됐다 — 로컬(`lo0`)이라 실질적 위협은 없지만, 같은 요청이 공인 네트워크를 평문 HTTP로 오갔다면 중간에서 누구나 이 내용을 그대로 읽을 수 있었다는 뜻. HTTPS(TLS)가 필요한 이유를 이 캡처 하나로 직접 확인한 셈.

---

## 통찰

- 지금까지 아무 생각없이 서버 켜야되니깐 서버 키고 로컬이랑 네트워크 서버랑도 구분 못하고 켜뒀었는데 네트워크 개념을 공부하고 프로세스/스레드/포트 개념이 실제 실행 중인 내 서버에서 어떻게 나타나는지 확인하니깐 무슨 일이 돌아가는지 어렴풋이 알겠고, HTTP가 평문 프로토콜이라는 것이 실감났다.
아직 네트워크와 os 기초가 제대로 잡혀있지 않아서 얻어가는게 적었지만 그 두 기본 개념에 대한 필요성을 느꼈다는 점에서 의미가 컸다.

## 업데이트

- **bare 모델 역전 (9주차 실험 이어짐)**: graph(claude 고정) + verify 기준·출력 이원화 구성이 **0.926**으로 bare claude-haiku(**0.915**)를 처음으로 역전시킴 (`docs/README_09.md` 실험 5). 하락 원인이 파이프라인 원리 자체가 아니라 프리앰블·실패 고지로 인한 측정 오염과 verify의 "문서 근거성" 오판이라는 구현 문제였음이 확인됨 — 이번 10번 과제로 서버의 프로세스·네트워크 레벨 동작을 직접 들여다본 것과 이어서, 다음은 그 서버가 실제로 처리하는 요청·세션 구조 자체를 개선하는 단계로 넘어감.
- **단기기억 + 쓰레드 구현 완료 (07-20)**: `MemorySaver` checkpointer + `thread_id`로 유저별 멀티턴 대화 세션 분리. 구현 포인트:
  - `thread_id`를 FastAPI `Query` 필드로 추가 — 같은 값으로 요청하면 대화 이력이 이어지고, 생략 시 `uuid4` 자동 발급으로 단발 요청도 안전
  - **`reset_turn` 노드 신설 (START 직후)**: checkpointer는 messages만이 아니라 State 전체를 살리므로, 이전 턴의 try_count·fix_needed·comment·서킷 브레이커가 새 턴을 오염시킨다. 매 턴 진입 시 **messages만 보존하고 나머지 임시 상태를 전부 초기화**하는 턴 경계선으로 해결. generate의 질문 등록 조건도 `if not history`(멀티턴에서 영원히 거짓)에서 `try_count==0`으로 교체 — 두 변경이 짝이 되어야 2번째 턴부터의 질문이 이력에 정상 등록됨
  - verify에 명확화 기준 추가: 맥락상 답할 수 없는 모호한 질문(예: 요약 대상이 대화에 없음)에 명확화를 요청한 답변은 정확한 대응이므로 반려하지 않음 — 멀티턴 특유의 불완전 질문 대비
  - `tokens_used` 추적 추가 (input/output/total, 노드 누적) — 이후 verify 구성 비교 실험의 토큰 지표로 사용 예정
  - 남은 것: 메시지 트리밍(긴 대화 토큰 성장 관리), 후속 질문 재작성(짧은 후속 질문이 그대로 벡터 검색어가 되는 문제), SqliteSaver 영속화(MemorySaver는 프로세스 메모리라 서버 재시작 시 소멸 — 이번 과제에서 관찰한 "프로세스"의 생명주기와 정확히 같은 운명)
