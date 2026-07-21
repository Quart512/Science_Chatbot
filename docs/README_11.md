# 11주차 과제 — Docker 패키징 + Compose + EC2 배포 + CI/CD

> 과제 원문: (1) 개인 프로젝트를 Docker 컨테이너로 패키징하고 Docker Compose로 실행 (2) 컨테이너 이미지를 AWS EC2에 배포해 외부에서 접근 가능하도록 구성 (3) GitHub Actions로 push 시 자동 빌드·배포되는 CI/CD 파이프라인 구축

대상 프로젝트: `Science_Chatbot` — FastAPI(`science-chatbot`) + 파인튜닝 Qwen 모델 서빙(`llama-server`, 선택적 컨테이너)

진행 상황: **(1) 완료** / **(2) 완료** — EC2 배포 + 외부 접근 검증까지 마침 / (3) 예정

---

## 1. Docker 패키징 — Dockerfile

### 1.1 설계 포인트

```dockerfile
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN uv sync --no-install-project --frozen

COPY ./ ./
RUN uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

| 결정 | 이유 |
|---|---|
| `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/` | uv를 별도 설치 과정 없이, uv 공식 이미지 안에 이미 컴파일된 바이너리를 그대로 복사(멀티스테이지 COPY) — 설치 시간 단축 |
| 의존성 설치를 두 단계로 분리 (`pyproject.toml`+`uv.lock`만 먼저 COPY → sync → 전체 COPY → 다시 sync) | Docker 레이어 캐싱 활용 — 코드만 바뀐 날엔 무거운 의존성 재설치 레이어가 캐시에서 재사용됨 |
| 첫 `uv sync`에 `--no-install-project` | 아직 전체 소스(및 `pyproject.toml`이 참조하는 `README.md`)가 없는 시점이라 프로젝트 자체 설치는 생략, 의존성만 먼저 설치 |
| `--frozen` | `uv.lock`에 적힌 버전을 그대로 재현 — lock과 안 맞으면 조용히 재계산하지 않고 에러 |
| `CMD`에 `--host 0.0.0.0` 명시 | 기본값 `127.0.0.1`은 컨테이너 내부에서만 보이는 주소라 포트 매핑을 해도 외부에서 접속 불가 — 모든 인터페이스에서 받도록 명시 필요 |

### 1.2 .dockerignore

```
docs/
.git/
.venv/
evaluation/results/
.env
```

`.env`는 `COPY ./ ./`로 이미지에 그대로 구워지면 실제 API 키가 이미지 레이어에 영구히 남는 보안 문제라 반드시 제외. `docs/`는 컨테이너 실행에 전혀 필요 없는 문서라 빌드 컨텍스트 자체에서 제외(빌드 시점에 아예 인식되지 않음 — 런타임에 볼륨으로 채워지는 것과는 다른 배제 방식).

---

## 2. Docker Compose — 다중 컨테이너 구성

### 2.1 설계 변경 — Qwen-tuned를 별도 컨테이너로 분리

원래 계획은 RAM 제약(EC2 프리티어) 때문에 파인튜닝 모델(`Qwen-tuned`, llama-server) 자체를 배포에서 제외하는 것이었으나, **선택적으로 켤 수 있는 별도 컨테이너**로 분리하는 쪽으로 변경 — EC2 RAM 부담 없이 필요할 때만 실행 가능하고, 컨테이너 간 통신도 실습할 수 있어서.

```yaml
services:
  science-chatbot:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - LOCAL_MODEL_URL=http://llama-server:8080/v1
    volumes:
      - "./chroma_db:/app/chroma_db"
      - "huggingface-cache:/root/.cache/huggingface"

  llama-server:
    command: -m /app/models/qwen_finetuned_Q4_K_M.gguf --port 8080 --host 0.0.0.0
    image: ghcr.io/ggml-org/llama.cpp:server
    ports:
      - "8080:8080"
    volumes:
      - "./models:/app/models"
    profiles: ["llama"]

volumes:
  huggingface-cache:
```

### 2.2 핵심 개념 정리

| 개념 | 내용 |
|---|---|
| `profiles: ["llama"]` | `docker compose up`(profile 없이)엔 `llama-server`가 아예 시작되지 않음. `docker compose --profile llama up`으로 명시했을 때만 실행 — 선택적 기동 |
| `image:` vs `build:` | `llama-server`는 공식 사전 빌드 이미지(`ghcr.io/ggml-org/llama.cpp:server`)를 그대로 쓰므로 Dockerfile이 필요 없음. Dockerfile은 "새 이미지를 만들 때"만 필요하고, 이미 완성된 이미지를 그대로 실행할 땐 `image:`로 참조만 하면 됨 |
| `command:` | 이미지의 `ENTRYPOINT`(이미 `llama-server` 바이너리로 고정)에 붙는 인자만 지정 — 실행 파일 이름을 다시 적으면 중복. 리스트로 한 문자열을 통째로 넣으면 인자 하나로 뭉쳐 인식되므로, 공백으로 자동 분리되는 문자열 형태로 작성 |
| 바인드 마운트 (`./models:/app/models`) | GGUF 모델 파일(941MB)을 이미지에 굽지 않고 런타임에 호스트 파일을 컨테이너에 연결 — 이미지 크기를 키우지 않고, 모델 교체도 재빌드 없이 가능 |
| 네임드 볼륨 (`huggingface-cache:/root/.cache/huggingface`) | bge-m3 임베딩 모델 캐시(~2GB)를 Docker가 관리하는 별도 저장소에 유지 — 컨테이너를 재생성해도 매번 재다운로드하지 않음 |
| 컨테이너 간 통신 = 서비스 이름 기반 DNS | `science-chatbot`이 `llama-server`를 부를 때 `localhost:8080`이 아니라 `http://llama-server:8080/v1`로 접속 — 컨테이너 안에서 `localhost`는 자기 자신을 가리키므로, Compose가 만들어주는 내부 네트워크에서는 서비스 이름 자체가 호스트네임으로 resolve됨 |
| `environment:` vs `env_file:` | 같은 키가 둘 다에 있으면 `environment:`가 우선 적용됨. `.env`는 로컬 직접 실행(`uv run`)과 공유되는 파일이라 로컬 기본값(`localhost:8080`)을 유지하고, Compose 실행 시에만 `LOCAL_MODEL_URL`을 `environment:`로 덮어써서 두 실행 환경을 분리 |
| `ports:`가 컨테이너 간 통신엔 불필요한 이유 | `llama-server`의 `"8080:8080"` 매핑은 호스트(맥)에서 직접 `curl`로 찔러볼 때만 필요 — science-chatbot이 내부 네트워크로 직접 접속하는 경로와는 별개 |

### 2.3 검증 — science-chatbot 단독 기동

```
docker compose up --build
```

빌드 17/17 스텝 성공, 컨테이너 정상 기동:
```
science-chatbot-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```
호스트에서 `curl http://localhost:8000/docs`로 포트 매핑 확인 완료.

### 2.4 검증 — 컨테이너 간 통신 (llama-server 포함)

```
docker compose --profile llama up --build
```

```
llama-server-1  | ... llama_server: loading model '/app/models/qwen_finetuned_Q4_K_M.gguf'
llama-server-1  | ... llama_server: model loaded
llama-server-1  | ... llama_server: listening on http://0.0.0.0:8080
```

실제 쿼리(`model: "Qwen-tuned"`)를 보낸 결과, science-chatbot이 `llama-server:8080`으로 정상 접속해 응답을 받아왔고, 그 과정에서 Gemini 쿼터 소진(`429 RESOURCE_EXHAUSTED`) → claude fallback → verify 재시도 루프(4회) → 최종답변까지 기존 그래프 로직 그대로 동작함을 확인:

```
science-chatbot-1  | LLM 모델 사용: Qwen-tuned
...
science-chatbot-1  | langchain_google_genai.chat_models.ChatGoogleGenerativeAIError: ... 429 RESOURCE_EXHAUSTED ...
science-chatbot-1  | 모델 오류! fallback인 claude 모델로 전환
...
science-chatbot-1  | -----최종답변-----
science-chatbot-1  | INFO:     192.168.65.1:25935 - "POST /query HTTP/1.1" 200 OK
```

**결론: 컨테이너 간 통신, profiles 기반 선택적 기동, 기존 fallback/verify 로직 모두 Docker 환경에서 정상 동작 확인.** (답변 품질 자체는 1.5B 파인튜닝 모델의 한계이며 인프라 문제 아님)

---

## 3. 이미지 레지스트리 — Docker Hub

### 3.1 태깅과 레지스트리 주소

```
docker tag science_chatbot-science-chatbot:latest quart512/science-chatbot:latest
docker push quart512/science-chatbot:latest
```

`docker tag`는 이미지를 복제하지 않는다 — 같은 이미지 레이어(동일 Image ID)에 이름표를 하나 더 붙이는 것뿐. Docker 이미지 이름(`[레지스트리주소/]계정이름/저장소이름:태그`)은 그 자체로 "어디로 push할지"를 결정하는 주소 정보를 담고 있음. Git으로 비유하면, `git remote add origin <url>`처럼 이름(별명)과 실제 주소(url)가 분리된 게 아니라, **태그 문자열 자체가 곧 remote 주소** — 별도의 remote 등록 과정 없이 이름이 곧 목적지.

### 3.2 결과

```
The push refers to repository [docker.io/quart512/science-chatbot]
...
latest: digest: sha256:e73378d560fdff7cde5fedcf919e05b0c3bb5f7394c5363ba284147eb5e5b3f1 size: 856
```

Push 성공. 이미지 크기 8.78GB — `docker history`로 확인한 결과 `RUN uv sync --no-install-project --frozen` 레이어가 5.43GB로 대부분을 차지. 코드나 모델 가중치가 아니라 RAG·임베딩(bge-m3/sentence-transformers/torch 계열)과 Gemini/Claude SDK, chromadb, langchain 생태계 라이브러리 전체가 원인 — 추후 최적화 여지(불필요 extras 제거, CPU 전용 torch wheel 등)로 남겨둠.

---

## 4. EC2 배포 — 완료

- [x] 이미지 레지스트리(Docker Hub) push
- [x] EC2 인스턴스 생성 — `t4g.micro`(Graviton/arm64, 프리티어), Ubuntu 24.04 LTS **arm64** AMI. 로컬 이미지가 Apple Silicon 맥에서 arm64로 빌드됐기 때문에 인스턴스·AMI 아키텍처를 그에 맞춰 선택(불일치 시 실행 불가)
- [x] EC2에서 이미지 pull + `docker compose up` 실행
- [x] Security Group 8000/22 포트 오픈 (소스: 내 IP로 제한 — 10주차 WireShark 캡처로 확인한 HTTP 평문 노출 문제가 공인망에서는 실제 위협이 되므로)

### 4.1 트러블슈팅 — OOM으로 인한 컨테이너 강제 종료

첫 실행에서 컨테이너가 시작 직후 `Exited (137)`로 죽음 — 137(=128+9=SIGKILL)은 커널 OOM Killer의 전형적인 신호. `t4g.micro`의 RAM 1GB로는 bge-m3 임베딩 모델 로딩 순간의 메모리 스파이크를 못 버팀 (사전에 To Do List에 적어뒀던 위험이 실제로 발생).

**해결 — 스왑 2GB 추가**:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
적용 후 재시도하니 `Loading weights` → `Uvicorn running on http://0.0.0.0:8000`까지 정상 통과, 이후 `Exited` 없이 안정적으로 유지됨.

### 4.2 검증 — 외부에서 실제 쿼리 성공

```
science-chatbot-1  | INFO:     211.244.225.211:58865 - "GET /docs HTTP/1.1" 200 OK
science-chatbot-1  | 질문: 중력이란?
science-chatbot-1  | LLM 모델 사용: gemini
...
science-chatbot-1  | ---verify 단계 시작---
science-chatbot-1  | LLM 모델 사용: claude
science-chatbot-1  | 수정 필요한가: False
science-chatbot-1  | -----최종답변-----
science-chatbot-1  | INFO:     211.244.225.211:58866 - "POST /query HTTP/1.1" 200 OK
```

맥 브라우저/터미널에서 EC2 퍼블릭 IP로 `/docs`, `/query` 둘 다 정상 응답 확인 — Security Group의 "내 IP" 제한도 의도대로 동작(요청 출발지가 등록한 IP와 일치). gemini 생성 → claude 교차 verify까지 로컬과 동일한 그래프 로직이 EC2에서도 그대로 재현됨.

**참고**: `llama-server`(Qwen-tuned)는 이번엔 켜지 않음 — science-chatbot 하나만으로도 스왑을 동원해야 겨우 안정화된 RAM 상황이라, 동시 기동은 다음 단계로 미룸.

### 4.3 운영 노트 — 중지/재시작, 스토리지 구조, 모니터링 사각지대

**인스턴스 중지→재시작 시 체크리스트** (비용 절약을 위해 안 쓸 때 중지하는 경우):
- 퍼블릭 IP가 바뀐다(재부팅과 다름 — 중지 후 재시작 시 새 IP 배정). SSH·브라우저 접속 주소를 매번 새로 확인해야 함
- 컨테이너는 자동으로 안 켜짐 — `docker-compose.yml`에 `restart:` 정책을 안 넣어뒀으므로, 재접속 후 `docker compose up -d`를 다시 실행해야 함
- 스왑은 `/etc/fstab`에 등록해뒀으므로 재부팅해도 자동 재활성화(재설정 불필요)
- pull한 이미지·`.env`·`docker-compose.yml`은 EBS 볼륨(디스크)에 남아있으므로 재전송 불필요 — RAM에 상주하던 실행 상태만 사라짐

**Docker 데이터의 실제 저장 위치**: 컨테이너 안에서 보이는 `/app` 같은 경로는 실제로는 EC2 인스턴스와 별개의 저장공간이 아니라, 우리가 잡아준 **그 20GB EBS 루트 볼륨 안의** `/var/lib/docker/`(OverlayFS 레이어들이 겹쳐 보이는 형태)일 뿐. 이미지·컨테이너 쓰기 레이어·볼륨이 전부 이 하나의 디스크를 나눠 씀 — 스토리지 크기를 20GB로 늘렸던 이유가 여기서 실질적으로 소모됨. `docker system df`로 항목별 사용량 확인 가능.

**AWS 콘솔에서 메모리·스왑 사용량이 안 보이는 이유**: EC2 기본 모니터링(CloudWatch)은 하이퍼바이저 바깥에서 관찰 가능한 지표(CPU, 네트워크, EBS I/O)만 기본 제공 — RAM·스왑 사용량은 게스트 OS 내부 상태라 별도 CloudWatch Agent 설치 없이는 AWS 쪽에서 안 보임. 지금처럼 SSH로 `free -h` 직접 확인하는 게 가장 간단한 방법.

## 5. (예정) GitHub Actions CI/CD

- [ ] push 시 이미지 빌드 → 레지스트리 push → EC2 배포(SSH) 워크플로우
- [ ] `.env`/API 키는 GitHub Secrets로 관리, 절대 커밋 금지

---

## 업데이트

- 원래 To Do List엔 "Qwen-tuned(llama-server)는 RAM 부담으로 배포에서 제외"로 적혀 있었으나, 실습 도중 "제외" 대신 "선택적 컨테이너로 분리"로 설계를 바꿈 — 단순히 컨테이너 안 켜는 것보다, 컨테이너 간 통신이라는 배울 거리가 있는 방향을 택함. 결과적으로 Compose `profiles`, 서비스명 기반 DNS, `environment:`/`env_file:` 우선순위까지 원래 계획엔 없던 개념을 추가로 익힘.
- 다음 단계(EC2 배포)부터는 10주차에 직접 확인한 "HTTP는 평문"이라는 사실이 로컬 실습이 아니라 실제 공인망 노출 문제로 이어짐 — Security Group 설정 시 이 부분을 실질적 리스크로 다뤄야 함.
- To Do List에 미리 적어뒀던 "프리티어 RAM 1GB — bge-m3 로드 위험"이 추측이 아니라 실제로 재현됨(`Exited 137`, OOM Killer). 사전에 위험을 문서화해뒀던 덕분에 원인 파악이 빨랐음 — 스왑 2GB 추가로 해결, 상세는 [DEPLOY.md](../DEPLOY.md) 2.2.1 참고.
- EC2 실제 쿼리 로그를 들여다보다 `graph.py`의 사소한 로깅 버그 발견: `final_answer()`가 `try_count==1`(재시도 없이 첫 시도 통과)일 때는 지름길로 바로 `return`해서 `최종답변: ...` print가 없는 분기를 탐 — 재시도가 있었던 경우(else 분기)에만 그 print가 있었던 비일관성. RuntimeError 등 실제 오류는 아니었고(응답은 200 OK로 정상), 그 분기에도 print 추가해 수정.
