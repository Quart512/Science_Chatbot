# 배포 · 릴리즈 · 운영

**저자 본인이 나중에 배포 작업을 다시 할 때 보는 참고서**다. 앱을 쓰려는 사람은
[README.md](../README.md), 코드를 고치려는 사람은 [DEVELOPMENT.md](DEVELOPMENT.md)를 본다.

> 이 문서는 옛 `DEPLOY.md`를 대체한다. 그 문서는 "EC2에 앱을 Docker로 배포"하는 절차였는데,
> 08-05에 **EC2 배포 트랙이 폐지**되면서(앱은 사용자가 내려받아 자기 컴퓨터에서 실행,
> EC2는 랜딩 페이지만 서빙) 통째로 낡았다. 근거는 RoadMap 설계 노트 "EC2 배포 트랙 폐지".

---

## 지금 배포가 어떻게 굴러가는가

갈래가 셋이고 서로 독립적이다.

| 산출물 | 어디로 | 트리거 |
|---|---|---|
| **포터블 번들 zip 3종 + Docker zip** | GitHub Releases | `v*` 태그 push |
| **Docker 이미지** (`quart512/science-chatbot:latest`) | Docker Hub | `main` push |
| **랜딩 페이지** (정적 HTML) | EC2 + nginx | `landing/**` 변경 push |

---

## 1. GitHub Actions 워크플로우 지도

여섯 개가 있고, 서로 겹치는 부분이 있어 한 번에 보는 게 낫다.

| 워크플로우 | 트리거 | 하는 일 |
|---|---|---|
| `test.yml` | PR(main) + 다른 워크플로우가 `uses:`로 호출 | pytest. **재사용 워크플로우**라 스텝이 여기 한 곳에만 있다 |
| `build-bundle-{macos,linux,windows}.yml` | 해당 빌드 스크립트가 바뀐 PR + 수동 | 번들 빌드가 깨졌는지만 검증(산출물은 안 올림) |
| `deploy.yml` | `main` push | `test.yml` 통과 후 Docker 이미지를 amd64/arm64 **각각 네이티브 러너**에서 빌드해 digest만 push → `merge` job이 하나의 멀티아키 매니페스트로 합침 |
| `release.yml` | **`v*` 태그 push** + 수동 | 번들 3종 + Docker zip을 빌드해 GitHub Release 생성 |
| `deploy-landing.yml` | `landing/**` 변경 push + 수동 | Next.js 정적 빌드 → EC2로 rsync |

**`test.yml`이 두 군데서 도는 이유**: PR에 직접 붙어 머지 전에 결과가 보이고, `deploy.yml`이
같은 걸 `uses:`로 재호출해 배포 게이트로도 쓴다. 하나로 합치면 배포 직전 실패를 PR에서 미리 못 잡는다.

**`deploy.yml` 이름이 낡았다** — `Publish Science Chatbot Image`인데 저장소명이 `AIsaac`으로
바뀌었고 EC2 배포도 이미 빠졌다(지금은 Docker Hub push까지만 한다). 이미지 이름
`quart512/science-chatbot`도 그대로다 — 바꾸면 기존 `docker-compose.yml`이 가리키는 태그가
깨지므로 **일부러 안 건드렸다**.

---

## 2. 포터블 번들 빌드 (로컬)

```bash
bash scripts/build_bundle_macos.sh      # → build/AIsaac/ (Apple Silicon 전용)
bash scripts/build_bundle_linux.sh      # → build/AIsaac/ (x86_64)
pwsh scripts/build_bundle_windows.ps1   # → build/AIsaac/ (x86_64)
```

세 스크립트가 같은 구조다: 프론트 빌드 → `uv sync --no-dev`로 **별도 폴더**에 의존성 설치
→ 독립 실행 파이썬 복사 → 앱 소스 화이트리스트 복사 → 실행 스크립트 생성 → **검증**.

**주의할 함정 세 가지** (전부 실제로 겪은 것):

- **화이트리스트를 빠뜨리면 사용자 실행 시점에야 터진다.** 그래서 빌드 끝에 번들 자신의
  파이썬으로 `import main`을 돌려 실패하면 빌드를 실패시킨다. 루트에 `.py`를 새로 추가하면
  세 스크립트의 화이트리스트에 같이 넣어야 한다.
- **프론트 `dist`는 공유 가변 산출물이다.** 오버라이드 없는 맨 `npm run build`가 끼어들면
  `http://localhost:8000`이 박힌 dist가 번들에 실려 API가 전부 CORS로 막힌다. 이제
  `frontend-react/.env.production`이 근본적으로 막고, 빌드 스크립트도 dist에 절대 URL이
  남아 있으면 실패시킨다.
- **Intel Mac 번들은 원리적으로 불가능하다.** `onnxruntime`이 이 프로젝트가 요구하는 파이썬
  버전용 macOS x86_64 wheel을 안 만든다. Intel Mac 사용자의 유일한 경로는 Docker다.

---

## 3. 릴리즈 내기

```bash
# 1) 릴리즈 노트를 먼저 쓴다 (없으면 커밋 로그 자동 요약으로 폴백)
cp docs/releases/TEMPLATE.md docs/releases/v0.1.0.md
#    → 내용은 RoadMap 완료 표에서 그 기간 항목을 추려 요약

# 2) 태그를 push하면 release.yml이 전부 알아서 한다
git tag v0.1.0
git push origin v0.1.0
```

`release.yml`이 macOS/Windows/Linux 번들 3종 + Docker zip을 각 OS 러너에서 빌드해
`gh release create`로 올린다. `docs/releases/<태그>.md`가 있으면 그걸 릴리즈 본문으로 쓰고,
없으면 `--generate-notes`로 폴백한다.

**안전장치**: 실제 Release 생성 스텝에 `if: startsWith(github.ref, 'refs/tags/')`가 걸려 있어
`workflow_dispatch`(수동 실행)로는 빌드 검증까지만 되고 **공개 Release는 안 만들어진다.**
태그를 실제로 push하는 것이 공개 게시의 유일한 방아쇠다.

> **아직 한 번도 실제 태그를 push한 적이 없다**(08-07 기준). 그래서 랜딩 페이지의
> 다운로드 링크(`releases/latest/download/...`)는 첫 릴리즈 전까지 404다 — 코드 문제가
> 아니라 릴리즈 프로세스가 아직 안 끝난 것.

---

## 4. 랜딩 페이지 (EC2)

`landing/`은 Next.js `output: "export"`로 뽑은 **순수 정적 파일**이라 EC2에서 돌릴 Node
프로세스가 없다 — nginx가 파일을 그대로 서빙한다.

### 현재 인스턴스

| 항목 | 값 |
|---|---|
| 타입 | `t4g.nano` (Graviton/arm64, 프리티어 대상 아님 — 시간당 약 $0.0052) |
| OS | Ubuntu 26.04 LTS (arm64) |
| 웹서버 | nginx (`/etc/nginx/sites-available/aisaac-landing`) |
| 웹루트 | `/var/www/aisaac` |
| 보안그룹 | 22(SSH), 80(HTTP) |

주소는 GitHub 시크릿 `EC2_HOST`에 있다. 인스턴스를 중지 후 재시작하면 퍼블릭 IP가
바뀌므로(재부팅만 하면 안 바뀜) 그때 시크릿도 같이 갱신해야 한다 — 고정이 필요하면 Elastic IP.

### 최초 1회 수동 설정

```bash
ssh -i <키페어>.pem ubuntu@<EC2_HOST>
sudo apt update && sudo apt install -y nginx
sudo mkdir -p /var/www/aisaac && sudo chown ubuntu:ubuntu /var/www/aisaac
```

`landing/deploy/nginx.conf.example`을 `/etc/nginx/sites-available/aisaac-landing`으로 복사하고
`sites-enabled`에 심볼릭 링크한 뒤 `sudo nginx -t && sudo systemctl reload nginx`.
기본 사이트(`sites-enabled/default`)는 지운다.

필요한 GitHub 시크릿 3개: `EC2_HOST`, `EC2_SSH_KEY`(pem 전체 내용), `EC2_LANDING_PATH`(`/var/www/aisaac`).

### ⚠️ 지금 막혀 있는 것 — SSH 보안그룹

`deploy-landing.yml`이 **계속 실패한다**:

```
ssh: connect to host *** port 22: Operation timed out
rsync error: unexplained error (code 255)
```

원인은 보안 설정이 의도대로 동작한 결과다 — SSH 인바운드가 **저자 본인 IP로 제한**돼 있는데,
GitHub Actions 러너는 매번 다른 Azure 데이터센터 IP에서 접속하므로 22번 포트에 못 들어온다.

**해결하려면 둘 중 하나**:
- SSH 소스를 `0.0.0.0/0`으로 연다. 실제 방어선은 IP 제한이 아니라 **키 기반 인증**이고
  (Ubuntu 클라우드 이미지는 비밀번호 로그인이 기본 비활성), 이게 표준적인 절충안이다.
- GitHub Actions 공개 IP 대역만 허용한다 — 대역이 자주 바뀌고 범위가 넓어 관리 부담이 크다.

그 전까지는 로컬에서 직접 밀어넣는 게 유일한 배포 경로다:

```bash
cd landing && npx pnpm@9 install --frozen-lockfile && npx pnpm@9 exec next build
rsync -az --delete -e "ssh -i <키페어>.pem" out/ ubuntu@<EC2_HOST>:/var/www/aisaac/
```

> `pnpm`은 이 저장소에 devDependency로 없어서 `npx pnpm@9`로 부른다. **버전을 9로 고정하는
> 게 중요하다** — 최신(11.x)은 이 저장소의 lockfile을 `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH`로
> 거부한다(CI도 `pnpm/action-setup@v4` + `version: 9`로 같은 버전을 쓴다).

---

## 참고

- 아키텍처·설계 판단의 근거는 [RoadMap.md](RoadMap.md)와 주차별 회고(`README_08` ~ `README_13`)에 있다.
- EC2·Docker·CI/CD를 처음 구축하던 시기의 기록은 [README_11.md](README_11.md)에 있다(지금 구조와는 다르지만 당시 판단 근거가 남아 있다).
