# 배포 가이드

두 가지 배포 방식을 다룬다. 실습·학습 목적으로 둘 다 정리했지만, 실제 운영은 Docker 방식을 권장한다(환경 일관성, 재현성, 컨테이너 격리).

| | 빅뱅 배포 | Docker 배포 |
|---|---|---|
| 방식 | EC2에 직접 접속해 코드를 pull하고 실행 | 이미지를 빌드→레지스트리 push→EC2에서 pull·실행 |
| 환경 재현성 | 낮음 (EC2에 직접 파이썬·의존성 설치) | 높음 (이미지 하나로 어디서든 동일) |
| 배포 중단 | 있음 (재시작 필요) | 있음 (이번 구성 기준, 무중단은 11주차 범위 밖) |
| Qwen-tuned 로컬 모델 | 같은 인스턴스에서 `llama-server` 직접 실행 | 별도 컨테이너 + Compose `profiles`로 선택 실행 |
| 적합한 상황 | 빠르게 한 번 띄워보고 싶을 때, 학습용 | 반복 배포, 여러 환경(로컬/서버) 일관성이 필요할 때 |

---

## 0. 공통 준비 — EC2 인스턴스

1. **아키텍처 확인부터** — 로컬(맥) Docker 이미지를 쓸 계획이면, 그 이미지가 arm64로 빌드됐는지 x86으로 빌드됐는지 먼저 확인(`docker history <이미지>`에서 `--arch` 값 확인). Apple Silicon 맥은 기본적으로 arm64 이미지가 빌드된다. EC2 인스턴스 타입(예: `t4g.micro`=arm64/Graviton, `t2.micro`/`t3.micro`=x86)과 **AMI 아키텍처**를 이미지와 반드시 맞춰야 한다 — 어긋나면 실행 자체가 안 됨.
2. **인스턴스 생성**: EC2 콘솔 → 인스턴스 시작 → Ubuntu LTS(최신보다 한 버전 이전 LTS 추천 — 생태계 호환성) → 인스턴스 타입 → 키페어 생성(`.pem`, 안전한 곳에 보관, 재발급 불가) → 네트워크 설정에서 보안 그룹 생성:
   - SSH(22): 소스를 "내 IP"로 제한
   - 앱 포트(8000): 사용자 지정 TCP, 소스는 필요에 따라 "내 IP" 또는 "Anywhere"(공개 서비스라면). **HTTP는 평문 프로토콜**이라(10주차 WireShark 캡처로 직접 확인) 공인망 노출 시 최소한 소스 제한 권장, 여유 되면 HTTPS
   - 스토리지: 기본 8GB는 부족할 수 있음(Docker 방식은 이미지만 8GB대) — 20GB 이상 권장(30GB까지 프리티어 무료)
3. **SSH 접속**:
   ```bash
   chmod 400 ~/경로/키페어이름.pem
   ssh -i ~/경로/키페어이름.pem ubuntu@<EC2_퍼블릭IP>
   ```
   퍼블릭 IP는 인스턴스를 중지 후 재시작하면 보통 바뀐다(재부팅만 하면 안 바뀜) — 고정이 필요하면 Elastic IP 고려.

---

## 1. 빅뱅 배포 (수동 실행)

```bash
# EC2 안에서
sudo apt update -y && sudo apt upgrade -y

# uv 설치
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# 코드 가져오기
git clone <레포주소>
cd Science_Chatbot

# 의존성 설치 (uv가 pyproject.toml에 맞는 파이썬도 자동 설치)
uv sync

# .env 준비 — git에 없으므로 직접 작성하거나 로컬에서 scp로 전송
scp -i ~/경로/키페어이름.pem .env ubuntu@<EC2_퍼블릭IP>:~/Science_Chatbot/

# 인덱싱 (최초 1회) — chroma_db가 없다면
uv run ingest.py

# 서버 실행 (외부 접속 가능하도록 --host 0.0.0.0 명시)
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

- `chroma_db/`가 이미 로컬에 구축돼 있다면 `uv run ingest.py` 대신 `scp -r`로 통째로 옮기는 게 더 빠르다.
- 세션 끊겨도 서버가 유지되려면 `nohup`, `tmux`, 또는 `systemd` 서비스 등록 필요(단순 실습이면 `tmux` 추천).
- 접속 확인: 브라우저 또는 `curl http://<EC2_퍼블릭IP>:8000/docs`

---

## 2. Docker 배포 (Compose, science-chatbot + llama-server 분리)

### 2.1 로컬(맥) — 이미지 빌드 & 레지스트리 push

```bash
# Dockerfile로 이미지 빌드 (docker-compose.yml의 build: . 가 실행됨)
docker compose build

# Docker Hub 로그인 (최초 1회)
docker login

# 태그 — 로컬 이미지에 레지스트리 주소용 이름표를 추가
docker tag science_chatbot-science-chatbot:latest <Docker_Hub_계정>/science-chatbot:latest

# push
docker push <Docker_Hub_계정>/science-chatbot:latest
```

`docker-compose.yml`의 `science-chatbot` 서비스엔 `build:`와 `image:`를 함께 적어둔다 — 로컬에선 `build:`로 소스에서 빌드하고, 서버에선 `image:` 이름으로 pull만 하기 위함(소스·Dockerfile을 서버에 옮길 필요 없음).

**로컬 개발 중 테스트** — push 전에 로컬에서 먼저 돌려보고 싶다면:
```bash
docker compose up --build              # science-chatbot만
docker compose --profile llama up --build   # llama-server(Qwen-tuned)까지 같이
```
EC2 쪽(2.4)의 `docker compose pull` + `up -d`와 다른 점: 로컬은 소스 코드가 있으니 `--build`로 직접 빌드하며 테스트하고, EC2는 소스가 없으니 이미 push된 이미지를 `pull`만 해서 실행한다.

### 2.2 EC2 — Docker 설치

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu
# 그룹 반영을 위해 재접속 필요 (exit 후 다시 ssh)
```

### 2.2.1 스왑 설정

`t4g.micro`(RAM 1GB)에서 bge-m3 임베딩 모델을 로드하면 **OOM Killer에 의해 컨테이너가 즉시 강제 종료된다**(`docker compose ps -a`에 `Exited (137)`로 표시 — 137 = 128+9 = SIGKILL). 옵션이 아니라 이 RAM 사양에선 사실상 필수 단계:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

free -h   # Swap 항목에 2.0Gi 잡혔는지 확인
```

스왑은 디스크 공간을 고정으로 예약해두지만(그만큼 볼륨 용량이 줄어듦), RAM 자체는 부족할 때만 동적으로 그 디스크를 빌려 쓰는 방식이라 평소엔 오버헤드가 없다. 다만 디스크가 RAM보다 훨씬 느리므로 상시 스와핑에 의존하는 상황이라면(가끔의 로딩 스파이크가 아니라 지속적 부족) 인스턴스 사양을 올리는 게 근본 해결책.

### 2.3 필요한 파일만 EC2로 전송

Docker 방식은 소스 코드나 Dockerfile이 EC2에 필요 없다 — `docker-compose.yml`(설정 파일)과 `.env`(비밀값)만 옮기면 된다. **주의**: `docker-compose.yml`은 Docker Hub를 거치지 않는 일반 텍스트 파일이라 `scp`로 직접 복사해야 한다(이미지처럼 `pull`로 받아지지 않음).

```bash
# EC2 쪽에 디렉토리 생성
ssh -i ~/경로/키페어이름.pem ubuntu@<EC2_퍼블릭IP> "mkdir -p ~/science-chatbot"

# 맥에서 파일 전송 (Science_Chatbot 디렉토리에서 실행)
scp -i ~/경로/키페어이름.pem docker-compose.yml ubuntu@<EC2_퍼블릭IP>:~/science-chatbot/
scp -i ~/경로/키페어이름.pem .env ubuntu@<EC2_퍼블릭IP>:~/science-chatbot/

# chroma_db가 이미 구축돼 있다면 이것도 전송 (없으면 EC2에서 uv 없이 ingest 불가 — 별도 컨테이너로 돌리거나 사전에 옮겨야 함)
scp -i ~/경로/키페어이름.pem -r chroma_db ubuntu@<EC2_퍼블릭IP>:~/science-chatbot/
```

### 2.4 EC2 — pull & 실행

```bash
cd ~/science-chatbot
docker compose pull        # image: 이름으로 Docker Hub에서 완성된 이미지만 받아옴 (빌드 없음)
docker compose up -d       # 백그라운드 실행

# (선택) Qwen-tuned 로컬 모델까지 같이 띄우려면
docker compose --profile llama up -d
```

- `llama-server`까지 띄울 경우 EC2 RAM 여유를 반드시 확인 — 프리티어(1GB)는 bge-m3 임베딩 로드만으로도 빠듯할 수 있다.
- 접속 확인: `curl http://<EC2_퍼블릭IP>:8000/docs`

### 2.5 갱신 (코드 수정 후 재배포)

```bash
# 로컬
docker compose build
docker push <Docker_Hub_계정>/science-chatbot:latest

# EC2
docker compose pull
docker compose up -d   # 새 이미지로 컨테이너 재생성
```

---

### 2.6 인스턴스 중지 → 재시작 (비용 절약)

```bash
# 콘솔 또는 CLI로 인스턴스 중지, 필요할 때 다시 시작
```

재시작 후 체크리스트:
1. **퍼블릭 IP가 바뀐다** (재부팅과 다름) — EC2 콘솔에서 새 IP 확인 후 SSH·접속 주소 갱신
2. **컨테이너는 자동으로 안 켜짐** — 재접속 후 `cd ~/science-chatbot && docker compose up -d` 다시 실행
3. **스왑은 그대로 유지됨** — `/etc/fstab`에 등록해뒀으므로 재설정 불필요
4. **이미지·`.env`·`docker-compose.yml`은 EBS에 남아있음** — 재전송 불필요, RAM 상주 상태만 초기화됨
5. **GitHub Actions CI/CD를 쓰는 경우, `EC2_HOST` Secret도 새 IP로 갱신해야 함** — 저장소 Settings → Secrets and variables → Actions → `EC2_HOST` → Update. 안 하면 다음 push 시 워크플로우의 SSH 배포 단계가 예전 IP로 접속을 시도하다 실패함. (근본 해결책은 Elastic IP로 고정하는 것 — 자동화 파이프라인이 있다면 이 시점부터 Elastic IP의 실익이 커짐)

## 3. CI/CD(GitHub Actions) 사용 시 — 로컬 vs EC2, 뭐가 자동으로 바뀌나

`deploy.yml`이 `main` push마다 하는 일: GitHub 러너에서 코드 체크아웃 → 이미지 빌드 → Docker Hub push → EC2에 SSH 접속해 `docker compose pull` + `up -d`. **로컬(맥)은 이 흐름에 전혀 관여하지 않는다** — GitHub 러너가 로컬 파일을 읽는 게 아니라 push된 git 커밋을 자기 서버에서 체크아웃해 새로 빌드하는 것이고, 결과물도 로컬로 내려오지 않는다.

| | git push 시 자동 갱신? | 최신화하려면 |
|---|---|---|
| EC2 (실서비스) | O — `deploy.yml`이 자동으로 pull + 재시작 | 아무것도 안 해도 됨 |
| 로컬 (맥) | X | `docker pull <이미지>` 또는 `docker compose build`로 직접 |

로컬은 보통 매번 맞출 필요 없다 — 로컬의 역할은 "배포된 이미지를 그대로 쓰는 것"이 아니라 "소스 코드로 직접 빌드해서 테스트하는 것"(`docker compose up --build`)이기 때문이다. 로컬에 최신 이미지를 굳이 pull 받는 경우는 프로덕션에서만 나는 문제를 로컬에서 그대로 재현해보고 싶을 때 정도.

### 이미지·컨테이너 확인하는 법

**이미지 목록**: `docker images`
- 태그(`REPOSITORY:TAG`), `IMAGE ID`, 크기를 보여준다.
- `REPOSITORY`/`TAG`가 `<none>`으로 뜨는 항목이 dangling 이미지(아래 참고) — 이름표를 잃었을 뿐 삭제된 건 아니라 디스크는 그대로 차지한다.

**컨테이너 목록**: `docker ps` (실행 중인 것만) / `docker ps -a` (멈춘 것 포함 전체)
- `IMAGE` 컬럼으로 어떤 이미지 ID를 물고 쓰는 컨테이너인지 확인 가능.
- `STATUS` 컬럼으로 `Up`(실행 중) / `Exited`(정지) 구분.

이 두 명령으로 "지금 뭐가 남아있고, 뭐가 실제로 돌고 있는지"부터 확인하는 게 정리의 출발점이다.

### pull + up -d, 각각 뭘 건드리나 — 이미지·컨테이너·볼륨의 운명

> 로컬이든 EC2든 완전히 같은 Docker/Compose 엔진이 도는 것이라, 아래 동작은 환경과 무관하게 동일하다 — "로컬에서만 이런다"가 아니다.

**`docker compose pull`이 건드리는 건 이미지뿐**
- 레지스트리에서 `image:` 태그(예: `quart512/science-chatbot:latest`)가 가리키는 최신 digest를 확인하고, 로컬에 없는 레이어만 새로 받는다(레이어 캐싱 원리는 [README_11.md](README_11.md) §1.2 참고).
- 다 받으면 로컬의 `latest` 태그 포인터를 새 이미지로 옮긴다.
- **컨테이너는 이 시점에 전혀 안 건드린다** — 기존 컨테이너는 여전히, 방금 태그가 떨어져나간(dangling된) 예전 이미지로 계속 돌아가는 중이다.

**`docker compose up -d`가 건드리는 건 컨테이너**
- Compose가 "지금 떠 있는 컨테이너가 물고 있는 이미지"와 "지금 `image:` 태그가 가리키는 이미지"를 비교한다.
- 다르면(pull 직후엔 항상 다름) 기존 컨테이너를 **stop → remove**하고, 새 이미지로 컨테이너를 **create → start**한다. 두 컨테이너가 동시에 떠 있는 게 아니라 완전한 교체(새 컨테이너 ID) — 기존 컨테이너는 이 순간 사라진다.

**볼륨은 이 둘 중 어디에도 안 끼어든다**
- `./chroma_db`, `./models` 같은 바인드 마운트도, `huggingface-cache` 네임드 볼륨도 컨테이너 생명주기와 완전히 분리된 존재라 pull에도, up -d의 컨테이너 교체에도 영향을 안 받는다.
- 새로 만들어진 컨테이너는 `docker-compose.yml`에 적힌 그대로 같은 볼륨을 다시 마운트해서 시작 — 데이터는 컨테이너가 몇 번을 교체되든 그대로 이어진다(애초에 [README_11.md](README_11.md) §7에서 볼륨을 따로 뺀 이유가 이것 — 컨테이너는 갈아치우더라도 데이터는 안 날아가게).

| 오브젝트 | `pull`이 하는 일 | `up -d`가 하는 일 | 최종 상태 |
|---|---|---|---|
| 이미지 | 변경된 레이어만 받고 태그를 새 digest로 이동 | (관여 안 함) | 새 이미지 = 현재 태그, 예전 이미지 = dangling으로 디스크에 남음 |
| 컨테이너 | (관여 안 함, 예전 이미지로 계속 실행 중) | 예전 컨테이너 stop+remove → 새 이미지로 새 컨테이너 create+start | 예전 컨테이너는 완전히 사라짐 |
| 볼륨(바인드/네임드) | (관여 안 함) | (관여 안 함 — 새 컨테이너가 그대로 재마운트) | 그대로 유지, 데이터 연속 |

### 옛날 이미지·컨테이너는 자동 정리 안 됨

위 표의 "이미지" 행이 실제로 EC2에서 문제가 되는 사례다. 같은 태그(`latest`)로 새 이미지가 pull되면 태그 이름표만 새 이미지로 옮겨가고, 예전 이미지는 dangling(`<none>:<none>`) 상태로 디스크에 그대로 남는다. EC2처럼 디스크가 작으면(프리티어 기본 용량) 이게 쌓여서 `no space left on device`로 pull 자체가 실패할 수 있다 — 실제로 겪은 문제.

```bash
docker rm <컨테이너>          # 그 이미지를 물고 있는 컨테이너부터 제거해야 이미지 삭제 가능
docker rmi <옛 이미지 ID>     # 또는 정리용으로 docker image prune -a
```

참고로 `Exited` 컨테이너는 완전히 멈춘 상태라 CPU·메모리는 안 쓰고 디스크만 차지하고, `Up` 컨테이너는 요청을 대기하며 임베딩 모델 등을 메모리에 올려둔 채 유지한다. 로컬에서 테스트 삼아 `docker compose up -d` 했다면 다 쓴 뒤 `docker compose down`(또는 `stop`)으로 내려주는 게 좋다 — `stop`은 컨테이너를 멈추기만 해서 `start`로 바로 재개할 수 있고, `down`은 컨테이너와 네트워크까지 삭제해서 다시 쓰려면 `up`으로 새로 만들어야 한다.

## 참고

- 컨테이너 간 통신(science-chatbot ↔ llama-server)은 `localhost`가 아니라 **서비스 이름**으로 이뤄진다(`http://llama-server:8080/v1`) — Compose가 만드는 내부 네트워크에서 서비스 이름이 곧 DNS 호스트네임.
- Docker 세부 설계(레이어 캐싱, `uv sync --frozen`, profiles, 바인드 마운트 vs 네임드 볼륨 등)는 [README_11.md](README_11.md) 참고.
