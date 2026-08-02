import os

# 로컬(uv run)에선 기본값(localhost)을 쓰고, Docker Compose로 뜰 땐 서비스 이름으로
# 오버라이드된다 — models.py의 LOCAL_MODEL_URL과 완전히 같은 패턴. 챗·논문·관심사
# 페이지가 전부 같은 백엔드를 호출하므로 각 파일에 복제하지 않고 여기 하나로 모은다.
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
