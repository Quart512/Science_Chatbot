# 1단계: 프론트 빌드(08-05, Docker 패키징 — RoadMap "설치 앱의 UI 실행 방식" 참고) —
# node_modules(89MB)가 최종 이미지에 전혀 안 들어가게 별도 스테이지로 분리한다.
# 이 스테이지의 결과물(dist/)만 아래에서 COPY --from으로 가져간다.
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend-react
COPY frontend-react/package.json frontend-react/package-lock.json ./
RUN npm ci
COPY frontend-react/ ./
RUN npm run build

# 2단계: 백엔드 — uv 공식 이미지 안의 컴파일된 바이너리를 그대로 복사(별도 설치 과정 없이 uv 사용 가능)
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 의존성 설치를 두 단계로 분리 — 레이어 캐싱 활용
# 1단계: pyproject.toml/uv.lock만 먼저 복사 → 이 두 파일이 안 바뀌면 아래 RUN은 캐시 재사용
COPY pyproject.toml uv.lock ./

# --no-install-project: 아직 전체 소스(pyproject.toml이 참조하는 README.md 포함)가 없어서
#                        프로젝트 자체 설치는 생략, 의존성만 먼저 설치
# --frozen: uv.lock에 적힌 버전을 그대로 재현. lock과 안 맞으면 재계산 없이 에러
# --no-dev: dev 그룹(pytest·matplotlib) 제외 — 컨테이너 안에서는 테스트도 다이어그램
#           생성도 하지 않으므로 순수 낭비다(이미지 8.77GB→2.04GB 경량화의 연장선).
#           CI는 러너에서 직접 uv sync 후 pytest를 돌리므로 테스트 게이트와는 무관.
RUN uv sync --no-install-project --frozen --no-dev

# 2단계: 이제 전체 코드 복사 — 코드만 바뀐 재빌드에서는 위 1단계 레이어가 캐시로 재사용되고
#         여기서부터만 다시 실행됨(전체 재설치 안 함)
COPY ./ ./
RUN uv sync --frozen --no-dev

# 위 frontend-build 스테이지가 만든 산출물만 가져온다 — node_modules·소스는 안 남고
# dist만 들어가서 main.py의 StaticFiles가 이걸 서빙한다.
COPY --from=frontend-build /app/frontend-react/dist ./frontend-react/dist

EXPOSE 8000

# --host 0.0.0.0 필수 — 기본값 127.0.0.1은 컨테이너 내부에서만 보이는 주소라
# 포트 매핑을 해도 외부(호스트/인터넷)에서 접속 불가
#
# `uv run uvicorn ...`이 아니라 venv 바이너리를 직접 부른다(08-05 배포 검증 중 발견).
# `uv run`은 실행 **전에** lockfile 기준으로 환경을 동기화하는데 그 기본값이 dev 그룹
# 포함이라, 위 `uv sync --no-dev`로 애써 뺀 pytest·matplotlib을 컨테이너가 뜰 때마다
# 다시 설치했다(실제 로그에서 matplotlib·pillow·fonttools 다운로드 확인). 부작용이 두
# 가지였다 — ① 매 기동마다 네트워크가 필요해 오프라인이면 아예 못 뜬다 ② 그만큼 시작이
# 느려진다. 배포판은 남의 컴퓨터에서 도는 것이라 둘 다 그냥 넘길 수 없다.
# 빌드 단계에서 venv가 이미 완성돼 있으므로 동기화 자체가 불필요하고, .venv/bin의
# 실행 파일은 shebang이 venv 파이썬을 가리켜 import 경로도 알아서 맞는다.
CMD [".venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
