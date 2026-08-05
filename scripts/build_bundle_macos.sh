#!/bin/bash
# AIsaac portable 번들 빌더 (macOS) — 08-05.
#
# Docker Desktop 없이 도는 배포판을 만든다. 08-04에 기각했던 "파이썬 얼리기
# (PyInstaller)"가 아니라, **독립 실행 파이썬 + 설치된 패키지를 폴더째 담는** 방식이다
# (A1111·ComfyUI의 Windows 포터블과 같은 접근 — RoadMap 설계 노트 "Electron 검토" 참고).
# torch를 걷어낸 뒤에야 현실적인 크기(압축 236MB)가 됐다.
#
# 번들 레이아웃을 **저장소 루트와 똑같이** 만드는 게 이 스크립트의 핵심 설계다:
#   AIsaac/
#     runtime/python/   독립 실행 파이썬
#     runtime/lib/      site-packages (--no-dev)
#     main.py, paper/, frontend-react/dist/ ...   ← 저장소 루트와 동일 구조
# 앱이 쓰는 `data/`·`./chroma_db`가 **CWD 기준** 상대 경로라서, start.command가 번들
# 루트로 cd하면 Docker의 WORKDIR=/app와 완전히 같은 환경이 된다 — 경로 관련 새 버그가
# 생길 여지를 없애려고 일부러 이렇게 맞췄다.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_ROOT="$REPO_ROOT/build"
BUNDLE="$BUILD_ROOT/AIsaac"

cd "$REPO_ROOT"

echo "==> 이전 빌드 정리"
rm -rf "$BUNDLE"
mkdir -p "$BUNDLE/runtime"

echo "==> 1/5 프론트엔드 빌드"
(cd frontend-react && npm ci --silent && npm run build)

echo "==> 2/5 프로덕션 의존성 설치 (--no-dev)"
# UV_PROJECT_ENVIRONMENT로 대상 venv를 따로 지정한다 — 이게 없으면 프로젝트의 .venv를
# --no-dev로 덮어써서 개발자의 pytest·matplotlib이 사라진다(빌드가 개발 환경을 망가뜨리면 안 됨).
BUILD_VENV="$BUILD_ROOT/venv"
rm -rf "$BUILD_VENV"
UV_PROJECT_ENVIRONMENT="$BUILD_VENV" uv sync --no-dev --frozen --quiet

PY_VERSION_DIR="$(basename "$(find "$BUILD_VENV/lib" -maxdepth 1 -name 'python*' | head -1)")"
cp -R "$BUILD_VENV/lib/$PY_VERSION_DIR/site-packages" "$BUNDLE/runtime/lib"

echo "==> 3/5 독립 실행 파이썬 복사"
# uv가 내려받아 둔 python-build-standalone 배포본을 그대로 쓴다. venv가 아니라 **원본
# 인터프리터**를 복사하는 게 중요하다 — venv는 pyvenv.cfg와 스크립트 shebang에 절대
# 경로가 박혀 있어 다른 기계로 옮기면 깨진다. 원본 인터프리터 + PYTHONPATH 조합은
# 경로에 무관하게 동작한다(08-05에 다른 경로로 복사해 실측 확인).
PYTHON_SRC="$(uv python list --only-installed --output-format json \
  | "$BUILD_VENV/bin/python" -c '
import json, sys
entries = json.load(sys.stdin)
# 프로젝트가 요구하는 3.14 계열 중 uv가 관리하는(경로가 uv 저장소 아래인) 것만 고른다.
for e in entries:
    path = e.get("path") or ""
    if e.get("version", "").startswith("3.14") and "/uv/python/" in path:
        # .../cpython-3.14-macos-aarch64-none/bin/python3.14 -> .../cpython-...-none
        print(path.rsplit("/bin/", 1)[0])
        break
')"
[ -n "$PYTHON_SRC" ] || { echo "독립 실행 파이썬(3.14)을 못 찾았습니다. 'uv python install 3.14'를 먼저 실행하세요."; exit 1; }
# -L(심볼릭 링크를 따라가 실제 내용을 복사)이 필수다. uv는 `cpython-3.14-...`(마이너 버전)를
# `cpython-3.14.5-...`(패치 버전)로 가리키는 심볼릭 링크로 두는데, -L 없이 복사하면 번들에
# **빌드한 사람 기계의 절대 경로를 가리키는 링크**만 들어가 다른 기계에서 통째로 깨진다
# (08-05 첫 빌드에서 실제로 재현 — runtime/python이 0B로 나와서 발견).
cp -RL "$PYTHON_SRC" "$BUNDLE/runtime/python"

echo "==> 4/5 앱 소스 복사"
# 화이트리스트 — 배포판에 들어갈 것만 명시한다. 블랙리스트로 하면 새 파일이 생겼을 때
# 조용히 딸려 들어간다(테스트·평가 스크립트·개발 문서가 사용자에게 배포되면 안 됨).
#
# 저장소 루트의 .py 중 **ingest.py만 일부러 뺀다** — 파인만 강의록 색인을 만드는
# 일회성 스크립트라 모듈이 아니고, import되는 순간 Chroma.from_texts가 실행된다.
# 나머지는 전부 런타임 모듈이다. 목록이 틀리면 아래 5/5의 스모크 테스트가 잡는다.
for item in main.py graph.py models.py orchestrator.py retrieval.py embeddings.py \
            tool.py interests.py knowledge_notes.py api_keys.py \
            arxiv_api.py paper_catalog.py paper_search.py paper_screening.py \
            paper_recommend.py reference_recommender.py research_workflow.py \
            research_sessions.py research_branches.py research_notes.py \
            equipment.py paper; do
    [ -e "$item" ] && cp -R "$item" "$BUNDLE/" || { echo "   빠진 파일: $item"; exit 1; }
done
mkdir -p "$BUNDLE/frontend-react"
cp -R frontend-react/dist "$BUNDLE/frontend-react/dist"

echo "==> 5/5 실행 스크립트 생성"
cat > "$BUNDLE/start.command" <<'LAUNCHER'
#!/bin/bash
# AIsaac 실행 — 더블클릭하세요.
cd "$(dirname "$0")"

if lsof -i :8000 -sTCP:LISTEN &> /dev/null; then
  echo "8000번 포트를 다른 프로그램이 이미 쓰고 있습니다."
  echo "그 프로그램을 종료한 뒤 다시 실행해주세요."
  read -p "엔터를 누르면 창이 닫힙니다..." _
  exit 1
fi

echo "AIsaac을 시작합니다..."
echo "(처음 실행이면 AI 임베딩 모델을 내려받느라 몇 분 걸릴 수 있습니다 — 정상입니다)"
echo
echo "  ※ 종료하려면 이 창을 닫거나 Ctrl+C 를 누르세요."
echo

# 준비되면 브라우저를 여는 감시자를 백그라운드로 띄우고, 서버는 포그라운드로 실행한다.
# 포그라운드가 핵심 — 창을 닫으면 서버도 같이 죽어서 Docker의 detached 컨테이너처럼
# 프로세스가 남지 않는다(그래서 이 번들엔 stop 스크립트가 없다).
(
  for _ in $(seq 1 180); do
    if [ "$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/health 2>/dev/null)" = "200" ]; then
      open "http://127.0.0.1:8000"
      exit 0
    fi
    sleep 2
  done
) &

# --host 127.0.0.1 — Docker판은 컨테이너 네트워킹 때문에 0.0.0.0이 필수였지만, 번들은
# 호스트에서 직접 도니 LAN에 노출할 이유가 없다(같은 와이파이의 다른 기기 접근 차단).
PYTHONPATH="runtime/lib" exec runtime/python/bin/python3 -m uvicorn main:app \
  --host 127.0.0.1 --port 8000
LAUNCHER
chmod +x "$BUNDLE/start.command"

cat > "$BUNDLE/README.txt" <<'READMEEOF'
AIsaac — 물리 연구 어시스턴트

실행: start.command 를 더블클릭하세요.
종료: 실행 중 열린 터미널 창을 닫거나 Ctrl+C.

처음 실행할 때는 AI 임베딩 모델(약 2GB)을 내려받으므로 몇 분 걸립니다.
두 번째부터는 바로 뜹니다.

AI 모델 API 키는 앱 안의 "설정" 화면에서 입력합니다.
데이터(논문·노트·대화 기록)는 이 폴더의 chroma_db/ 와 data/ 에 저장됩니다.
READMEEOF

echo "==> 검증: 번들이 스스로 import되는지"
# 화이트리스트가 틀리면 사용자가 start.command를 눌렀을 때야 ModuleNotFoundError로
# 드러난다 — 08-05 첫 빌드에서 실제로 research_branches.py 누락이 그렇게 발견됐다.
# 그래서 빌드가 끝나기 전에 번들 자신의 파이썬으로 main을 import해보고, 실패하면
# 빌드를 실패시킨다(깨진 번들이 애초에 만들어지지 않게).
(
  cd "$BUNDLE"
  PYTHONPATH="runtime/lib" runtime/python/bin/python3 -c "import main" 2>&1 | tail -5
  exit "${PIPESTATUS[0]}"
) || { echo "   번들 import 실패 — 위 오류를 보고 화이트리스트를 고치세요."; exit 1; }
echo "   OK"
# 부산물 하나가 실은 이득이다 — 이 import가 __pycache__(.pyc)를 미리 만들어두므로
# 사용자의 첫 실행에서 바이트코드 컴파일이 생략된다. 압축 후 크기 영향은 작고
# (227MB) 첫 인상에 직접 걸리는 시작 시간을 줄여주니 일부러 안 지운다.

# 번들 밖을 가리키는 절대 경로 심볼릭 링크가 있으면 다른 기계에서 깨진다.
if find "$BUNDLE" -type l -exec sh -c 'readlink "$1" | grep -q "^/"' _ {} \; -print | grep -q .; then
  echo "   절대 경로 심볼릭 링크가 남아있습니다 — 이식 불가:"
  find "$BUNDLE" -type l -exec sh -c 'readlink "$1" | grep -q "^/"' _ {} \; -print
  exit 1
fi

echo
echo "완료: $BUNDLE"
du -sh "$BUNDLE"
