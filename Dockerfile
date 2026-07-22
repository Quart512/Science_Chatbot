# uv 공식 이미지 안의 컴파일된 바이너리를 그대로 복사 — 별도 설치 과정 없이 uv 사용 가능
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 의존성 설치를 두 단계로 분리 — 레이어 캐싱 활용
# 1단계: pyproject.toml/uv.lock만 먼저 복사 → 이 두 파일이 안 바뀌면 아래 RUN은 캐시 재사용
COPY pyproject.toml uv.lock ./

# --no-install-project: 아직 전체 소스(pyproject.toml이 참조하는 README.md 포함)가 없어서
#                        프로젝트 자체 설치는 생략, 의존성만 먼저 설치
# --frozen: uv.lock에 적힌 버전을 그대로 재현. lock과 안 맞으면 재계산 없이 에러
RUN uv sync --no-install-project --frozen

# 2단계: 이제 전체 코드 복사 — 코드만 바뀐 재빌드에서는 위 1단계 레이어가 캐시로 재사용되고
#         여기서부터만 다시 실행됨(전체 재설치 안 함)
COPY ./ ./
RUN uv sync --frozen

EXPOSE 8000

# --host 0.0.0.0 필수 — 기본값 127.0.0.1은 컨테이너 내부에서만 보이는 주소라
# 포트 매핑을 해도 외부(호스트/인터넷)에서 접속 불가
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
