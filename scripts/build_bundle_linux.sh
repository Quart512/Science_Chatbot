#!/bin/bash
# AIsaac portable 번들 빌더 (Linux) — 08-06.
#
# scripts/build_bundle_macos.sh와 완전히 같은 접근(독립 실행 파이썬 + site-packages를
# 폴더째, RoadMap 설계 노트 "Electron 검토" 참고) — python-build-standalone이 macOS와
# 같은 POSIX 레이아웃(bin/python3.14)으로 Linux도 배포하므로 대부분의 로직을 그대로
# 옮길 수 있다. 다른 지점 둘:
# ① 런처 — macOS는 LaunchServices 응답성 문제 때문에 osacompile(진짜 Cocoa 앱)이
#    필요했지만, Linux 데스크톱은 그런 제약이 없다. 대신 "더블클릭 실행"의 표준이
#    freedesktop.org .desktop 항목(Terminal=false로 터미널 없이 실행)이라 그걸 쓴다.
# ② 브라우저 창 종료 감지 — macOS는 고정 프로필 재사용 시 Chrome 싱글턴 락 때문에
#    osascript로 "창이 남아있는지" 직접 물어봐야 했다. Linux엔 그런 IPC가 표준으로
#    없어서(데스크톱 환경마다 다름 — GNOME/KDE/XFCE), Windows 번들과 같은 선택을
#    했다: 매 실행마다 새 임시 프로필을 써서 싱글턴 충돌 자체를 없애고 `wait`을
#    그대로 믿는다.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_ROOT="$REPO_ROOT/build"
BUNDLE="$BUILD_ROOT/AIsaac"

cd "$REPO_ROOT"

echo "==> 이전 빌드 정리"
rm -rf "$BUNDLE"
mkdir -p "$BUNDLE/runtime"

echo "==> 1/5 프론트엔드 빌드"
# VITE_BACKEND_URL을 빈 문자열로 명시 오버라이드 — .env의 로컬 개발용 값이 그대로면
# Vite가 빌드 시점에 번들 JS에 박아 CORS 버그가 난다(08-06, macOS 번들 실기 테스트로
# 발견 — RoadMap "포터블 번들 실기 테스트로 발견한 크래시" 참고).
(cd frontend-react && npm ci --silent && VITE_BACKEND_URL= npm run build)

echo "==> 2/5 프로덕션 의존성 설치 (--no-dev)"
# UV_PROJECT_ENVIRONMENT로 대상 venv를 따로 지정 — 안 하면 프로젝트 .venv를 --no-dev로
# 덮어써서 개발자의 pytest 등이 사라진다(macOS 스크립트와 같은 이유).
BUILD_VENV="$BUILD_ROOT/venv"
rm -rf "$BUILD_VENV"
UV_PROJECT_ENVIRONMENT="$BUILD_VENV" uv sync --no-dev --frozen --quiet

PY_VERSION_DIR="$(basename "$(find "$BUILD_VENV/lib" -maxdepth 1 -name 'python*' | head -1)")"
cp -R "$BUILD_VENV/lib/$PY_VERSION_DIR/site-packages" "$BUNDLE/runtime/lib"

echo "==> 3/5 독립 실행 파이썬 복사"
# 하드코딩 대신 uv 자신에게 물어본다(uv 버전·환경마다 저장 위치가 달라질 수 있어서,
# macOS 스크립트와 같은 원칙).
PYTHON_SRC="$(uv python list --only-installed --output-format json \
  | "$BUILD_VENV/bin/python" -c '
import json, sys
entries = json.load(sys.stdin)
for e in entries:
    path = e.get("path") or ""
    if e.get("version", "").startswith("3.14") and "/uv/python/" in path:
        print(path.rsplit("/bin/", 1)[0])
        break
')"
[ -n "$PYTHON_SRC" ] || { echo "독립 실행 파이썬(3.14)을 못 찾았습니다. 'uv python install 3.14'를 먼저 실행하세요."; exit 1; }
# -L 필수 — uv가 마이너 버전(cpython-3.14-...)을 패치 버전(cpython-3.14.5-...) 심볼릭
# 링크로 두는데, -L 없이 복사하면 번들에 빌드한 기계의 절대경로를 가리키는 링크만
# 남아 다른 기계에서 깨진다(macOS 첫 빌드에서 실제로 재현된 문제).
cp -RL "$PYTHON_SRC" "$BUNDLE/runtime/python"

echo "==> 4/5 앱 소스 복사"
# macOS 스크립트와 완전히 같은 화이트리스트. ingest.py는 일부러 제외(import만으로
# Chroma.from_texts가 실행되는 일회성 스크립트).
for item in main.py graph.py models.py orchestrator.py retrieval.py embeddings.py \
            tool.py interests.py knowledge_notes.py api_keys.py chat_sessions.py \
            wikipedia_api.py \
            arxiv_api.py paper_catalog.py paper_search.py paper_screening.py \
            paper_recommend.py reference_recommender.py research_workflow.py \
            research_sessions.py research_branches.py research_notes.py \
            equipment.py paper; do
    [ -e "$item" ] && cp -R "$item" "$BUNDLE/" || { echo "   빠진 파일: $item"; exit 1; }
done
mkdir -p "$BUNDLE/frontend-react"
cp -R frontend-react/dist "$BUNDLE/frontend-react/dist"

echo "==> 5/5 조용한 런처 생성"
cat > "$BUNDLE/run.sh" <<'LAUNCHER'
#!/bin/bash
# AIsaac 실제 작업 — AIsaac.desktop이 Terminal=false로 이걸 호출한다.
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p logs

if (echo > /dev/tcp/127.0.0.1/8000) 2>/dev/null; then
  command -v zenity &> /dev/null && zenity --error --text="8000번 포트를 다른 프로그램이 이미 쓰고 있습니다. 그 프로그램을 종료한 뒤 다시 실행해주세요." 2>/dev/null
  exit 1
fi

PYTHONPATH="runtime/lib" runtime/python/bin/python3 -m uvicorn main:app \
  --host 127.0.0.1 --port 8000 >> logs/server.log 2>&1 &
SERVER_PID=$!

ready=false
for _ in $(seq 1 180); do
  if [ "$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/health 2>/dev/null)" = "200" ]; then
    ready=true
    break
  fi
  sleep 2
done

if [ "$ready" != "true" ]; then
  command -v zenity &> /dev/null && zenity --error --text="서버가 응답하지 않습니다. logs/server.log 를 확인해주세요." 2>/dev/null
  kill "$SERVER_PID" 2>/dev/null
  exit 1
fi

APP_URL="http://127.0.0.1:8000"
# 매 실행마다 새 임시 프로필 — Chrome/Chromium의 프로필 싱글턴 락(같은 프로필로 재실행
# 하면 새 창만 기존 프로세스에 얹고 새 프로세스는 곧장 종료됨, macOS에서 실측 확인된
# Chromium 공통 동작)을 피해 `wait`를 그대로 믿을 수 있게 한다 — Windows 번들과 같은
# 판단(로그인 세션이 재실행마다 안 남는 게 대가).
PROFILE_DIR="$(mktemp -d)"

BROWSER_BIN=""
for candidate in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge microsoft-edge-stable; do
  if command -v "$candidate" &> /dev/null; then
    BROWSER_BIN="$candidate"
    break
  fi
done

if [ -z "$BROWSER_BIN" ]; then
  # Chrome/Chromium/Edge 전부 없으면 기본 브라우저 탭으로 폴백 — 앱모드도, 창 종료
  # 감지도 못 하므로 서버는 계속 백그라운드에 남는다(다음 실행 시 포트 점유로 알아챔).
  command -v xdg-open &> /dev/null && xdg-open "$APP_URL" &
  disown "$SERVER_PID" 2>/dev/null
  exit 0
fi

"$BROWSER_BIN" --app="$APP_URL" --user-data-dir="$PROFILE_DIR" \
  --no-first-run --no-default-browser-check >> logs/browser.log 2>&1 &
BROWSER_PID=$!

wait "$BROWSER_PID" 2>/dev/null

kill "$SERVER_PID" 2>/dev/null
rm -rf "$PROFILE_DIR"
LAUNCHER
chmod +x "$BUNDLE/run.sh"

# AIsaac.desktop — freedesktop.org Desktop Entry(더블클릭 실행 표준). Terminal=false로
# 터미널 창 없이 실행된다. Exec에 절대경로가 필요해서(스펙상 %-확장 외 상대경로를
# 보장 안 함) 실제 절대경로는 사용자가 압축을 푼 뒤에야 정해지므로, run.sh 안에서
# 자기 위치를 스스로 찾게 하고 .desktop은 같은 폴더의 run.sh를 상대 문법으로
# 가리키는 대신 GNOME/KDE 대부분이 지원하는 %k(이 .desktop 파일 자신의 경로) 트릭 대신
# "같은 폴더에서 run.sh를 실행"하는 아주 짧은 셸을 Exec에 직접 심는다.
cat > "$BUNDLE/AIsaac.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=AIsaac
Comment=물리 연구 어시스턴트
Exec=bash -c 'cd "$(dirname "%k")" && ./run.sh'
Terminal=false
Categories=Education;Science;
DESKTOP
chmod +x "$BUNDLE/AIsaac.desktop"

cat > "$BUNDLE/README.txt" <<'READMEEOF'
AIsaac — 물리 연구 어시스턴트

실행: AIsaac.desktop을 더블클릭하세요.
  - 처음 실행할 땐 파일 관리자가 "신뢰할 수 없는 실행 파일"이라며 확인을 요구할
    수 있습니다(배포판마다 다름) — "실행" 또는 "허용"을 선택하세요.
  - 더블클릭이 안 먹으면 터미널에서 './run.sh'를 직접 실행해도 됩니다.
종료: 열린 브라우저 창을 닫으면 서버도 함께 종료됩니다.
로그: 문제가 있으면 logs/server.log 를 확인하세요.

처음 실행할 때는 AI 임베딩 모델(약 2GB)을 내려받으므로 몇 분 걸립니다.
두 번째부터는 바로 뜹니다.

AI 모델 API 키는 앱 안의 "설정" 화면에서 입력합니다.
데이터(논문·노트·대화 기록)는 이 폴더의 chroma_db/ 와 data/ 에 저장됩니다.
READMEEOF

echo "==> 검증: 번들이 스스로 import되는지"
# 화이트리스트가 틀리면 사용자가 실행했을 때야 ModuleNotFoundError로 드러난다(macOS
# 빌드에서 실제로 이렇게 발견된 전례). 빌드가 끝나기 전에 번들 자신의 파이썬으로 main을
# import해보고, 실패하면 빌드를 실패시킨다.
(
  cd "$BUNDLE"
  PYTHONPATH="runtime/lib" runtime/python/bin/python3 -c "import main" 2>&1 | tail -5
  exit "${PIPESTATUS[0]}"
) || { echo "   번들 import 실패 — 위 오류를 보고 화이트리스트를 고치세요."; exit 1; }
echo "   OK"

# 번들 밖을 가리키는 절대 경로 심볼릭 링크가 있으면 다른 기계에서 깨진다.
if find "$BUNDLE" -type l -exec sh -c 'readlink "$1" | grep -q "^/"' _ {} \; -print | grep -q .; then
  echo "   절대 경로 심볼릭 링크가 남아있습니다 — 이식 불가:"
  find "$BUNDLE" -type l -exec sh -c 'readlink "$1" | grep -q "^/"' _ {} \; -print
  exit 1
fi

echo
echo "완료: $BUNDLE"
du -sh "$BUNDLE"
