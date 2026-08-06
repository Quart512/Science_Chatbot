# 랜딩 페이지 EC2 배포 — 최초 1회 수동 설정

`.github/workflows/deploy-landing.yml`이 `main`에 `landing/**` 변경이 push될 때마다
자동으로 빌드해서 EC2로 동기화한다. 하지만 그 워크플로우가 동작하려면 EC2 쪽에
**미리 준비돼 있어야 하는 것**이 있다 — Claude Code는 이 EC2 인스턴스에 SSH 접속
권한이 없어서 아래는 사용자가 직접 해야 한다.

## 1. EC2에 nginx 설치 + 웹루트 생성

```bash
ssh ubuntu@<EC2_HOST>
sudo apt update && sudo apt install -y nginx
sudo mkdir -p /var/www/aisaac
sudo chown ubuntu:ubuntu /var/www/aisaac
```

`/var/www/aisaac`은 예시 경로 — 다른 경로를 쓰고 싶으면 아래 GitHub 시크릿
`EC2_LANDING_PATH`를 그 경로로 맞추면 된다.

## 2. nginx 사이트 설정

`deploy/nginx.conf.example`을 참고해 `server_name`·`root`를 실제 값으로 바꾼 뒤:

```bash
sudo cp nginx.conf.example /etc/nginx/sites-available/aisaac-landing
sudo ln -s /etc/nginx/sites-available/aisaac-landing /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

보안그룹에서 80번 포트(추후 443도)가 열려있는지 확인.

## 3. GitHub 저장소 시크릿 등록

Settings → Secrets and variables → Actions에서:

| 이름 | 값 |
|---|---|
| `EC2_HOST` | EC2 퍼블릭 IP 또는 도메인 |
| `EC2_SSH_KEY` | EC2 접속용 SSH 프라이빗 키 전체 내용 |
| `EC2_LANDING_PATH` | 1번에서 만든 웹루트 절대경로 (예: `/var/www/aisaac`) |

`EC2_HOST`·`EC2_SSH_KEY`는 예전 메인 앱 배포(`deploy.yml`, 08-05에 제거)에서
쓰던 것과 같은 이름이다 — 그때 등록해둔 게 아직 저장소에 남아있다면 재사용,
없다면 새로 등록.

## 4. 확인

위 세 단계가 끝나면 `landing/` 아래 아무 파일이나 커밋해서 `main`에 push하거나,
Actions 탭에서 "랜딩 페이지 배포 (EC2)" 워크플로우를 `workflow_dispatch`로 수동
실행해서 확인한다. 성공하면 `http://<EC2_HOST>`에서 바로 보인다(도메인 연결은
별도 항목, RoadMap "도메인 사기" 참고 — 지금은 무기한 연기).
