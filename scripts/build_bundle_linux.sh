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
            equipment.py library_order.py paper; do
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

BROWSER_BIN=""
for candidate in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge microsoft-edge-stable; do
  if command -v "$candidate" &> /dev/null; then
    BROWSER_BIN="$candidate"
    break
  fi
done

# 창모드 브라우저를 새로 연다. 호출마다 새 임시 프로필 — Chrome/Chromium의 프로필
# 싱글턴 락(같은 프로필로 재실행하면 새 창만 기존 프로세스에 얹고 새 프로세스는 곧장
# 종료됨, macOS에서 실측 확인된 Chromium 공통 동작)을 피해 `wait`를 그대로 믿을 수
# 있게 한다 — Windows 번들과 같은 판단(로그인 세션이 재실행마다 안 남는 게 대가).
# Chrome/Chromium/Edge 전부 없으면 일반 브라우저 탭으로 폴백(반환값 1).
open_window() {
  local url="$1"
  if [ -z "$BROWSER_BIN" ]; then
    command -v xdg-open &> /dev/null && xdg-open "$url" &
    return 1
  fi
  PROFILE_DIR="$(mktemp -d)"
  "$BROWSER_BIN" --app="$url" --user-data-dir="$PROFILE_DIR" \
    --no-first-run --no-default-browser-check >> logs/browser.log 2>&1 &
  BROWSER_PID=$!
  return 0
}

# 단일 인스턴스 가드(08-07) — data/·chroma_db/를 두 프로세스가 동시에 쓰면 SQLite는
# "database is locked"로, Chroma의 PersistentClient는 공식 문서가 명시하는 대로
# 멀티프로세스 동시 접근에 안전하지 않아 인덱스 손상까지 갈 수 있다. 아래 포트 자동
# 재시도가 생기기 전엔 두 번째 실행이 포트 충돌로 그냥 막혀서 이 위험이 우연히
# 차단돼 있었는데, 그 보호가 사라졌으니 여기서 직접 막는다 — 이미 살아있는 인스턴스가
# 있으면 새 서버 없이 그 포트로 창만 하나 더 열고 끝낸다. PID(kill -0)로 살았는지
# 확인하므로 비정상 종료로 lock만 남아도(크래시 등) 다음 실행이 정상적으로 새 서버를
# 띄운다.
LOCK_FILE="logs/server.lock"
if [ -f "$LOCK_FILE" ]; then
  EXISTING_PID="$(sed -n '1p' "$LOCK_FILE" 2>/dev/null)"
  EXISTING_PORT="$(sed -n '2p' "$LOCK_FILE" 2>/dev/null)"
  if [ -n "${EXISTING_PID:-}" ] && [ -n "${EXISTING_PORT:-}" ] && kill -0 "$EXISTING_PID" 2>/dev/null; then
    # 이 창은 추가 창일 뿐이라 원래 인스턴스의 서버 종료 감시(wait)에 안 얹는다 —
    # 곧장 백그라운드로 던지고 끝낸다(임시 프로필 정리는 생략, 드문 경로라 남는
    # 임시 폴더 하나 정도는 감수).
    open_window "http://127.0.0.1:$EXISTING_PORT"
    exit 0
  fi
fi

# /dev/tcp로 먼저 "비어있나?" 물어보고 나중에 uvicorn이 bind하는 방식은 그 사이에
# 다른 프로세스가 끼어들 수 있는 확인-후-사용 레이스(TOCTOU)라 8000이 막혀도 자동으로
# 복구가 안 됐다(macOS 스크립트와 같은 논의, 08-06). 대신 실제 bind를 직접 시도해
# 다음 포트로 넘어간다 — 소켓을 열어보는 것 자체가 곧 "비어있는지 확인"이라 별도
# 사전 체크와 결과가 어긋날 일이 없다. 8000~8049 안에서 못 찾으면 빈 문자열을 낸다.
PORT="$(runtime/python/bin/python3 -c '
import socket
for port in range(8000, 8050):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
    except OSError:
        continue
    finally:
        s.close()
    print(port)
    break
')"

if [ -z "$PORT" ]; then
  command -v zenity &> /dev/null && zenity --error --text="8000~8049번 포트를 전부 다른 프로그램이 쓰고 있어 실행할 수 없습니다." 2>/dev/null
  exit 1
fi

PYTHONPATH="runtime/lib" runtime/python/bin/python3 -m uvicorn main:app \
  --host 127.0.0.1 --port "$PORT" >> logs/server.log 2>&1 &
SERVER_PID=$!

ready=false
for _ in $(seq 1 180); do
  if [ "$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/api/health" 2>/dev/null)" = "200" ]; then
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

# 이 지점부터 서버가 살아있고 건강함 — 다음 실행이 단일 인스턴스 가드에서 찾을 수
# 있게 PID·포트를 기록한다.
printf '%s\n%s\n' "$SERVER_PID" "$PORT" > "$LOCK_FILE"

APP_URL="http://127.0.0.1:$PORT"

if ! open_window "$APP_URL"; then
  # 브라우저를 하나도 못 찾으면 앱모드도, 창 종료 감지도 못 하므로 서버는 계속
  # 백그라운드에 남는다(다음 실행 시 위 lock 검사가 재사용).
  disown "$SERVER_PID" 2>/dev/null
  exit 0
fi

wait "$BROWSER_PID" 2>/dev/null

kill "$SERVER_PID" 2>/dev/null
rm -f "$LOCK_FILE"
rm -rf "$PROFILE_DIR"
LAUNCHER
chmod +x "$BUNDLE/run.sh"

# AIsaac.desktop — freedesktop.org Desktop Entry(더블클릭 실행 표준). Terminal=false로
# 터미널 창 없이 실행된다. 사용자가 압축을 어디에 풀지 빌드 시점엔 모르므로 절대경로를
# 못 박아 넣는다 — 대신 %k(이 .desktop 파일 자신의 절대경로, 스펙에 정의된 필드 코드)를
# sh에 인자로 넘겨 실행 시점에 스스로 폴더를 찾게 한다.
#
# 08-06 첫 시도 실패 기록 — Exec에 `bash -c 'cd "$(dirname "%k")" && ./run.sh'`를 그대로
# 넣었다가 desktop-file-validate가 즉시 잡아냈다: Exec 값의 따옴표·이스케이프 규칙은
# **셸 문법이 아니라 Desktop Entry 스펙 자신의 규칙**이라 `&&`가 따옴표 밖에 있으면
# "reserved character" 에러가 나고, 필드 코드(%k)는 따옴표 "안"에 못 들어간다(스펙
# 명시: "Field codes must not be used inside a quoted argument"). 그래서 %k는 따옴표
# 밖(마지막 인자)으로 빼고, 셸 스크립트 본문만 따옴표로 감싸 그 안의 `"`·`$`만
# 스펙이 요구하는 대로 백슬래시 하나로 이스케이프했다(`&`·`(`·`)`는 따옴표 안에서는
# 이스케이프 불필요 — 실제로 desktop-file-validate 통과로 확인).
cat > "$BUNDLE/AIsaac.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=AIsaac
Comment=물리 연구 어시스턴트
Exec=sh -c "cd \"\$(dirname \"\$1\")\" && exec ./run.sh" sh %k
Terminal=false
Categories=Education;
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

echo "==> 검증: 프론트엔드가 같은 오리진을 쓰는지"
# 위 `import main`이 백엔드 화이트리스트에 대해 하는 일을 프론트엔드 환경변수에 대해
# 똑같이 한다. 08-07에 http://localhost:8000이 박힌 dist가 번들에 들어가 API 호출이
# 전부 CORS로 막힌 적이 있다 — 화면(정적 자산)은 멀쩡히 떠서 사용자 눈에는 원인 불명의
# "백엔드 연결 실패"로만 보였다.
#
# 정상 경로는 frontend-react/.env.production이 이미 막아뒀다(어떤 mode로 빌드하든 빈
# 값). 그럼에도 여기서 또 보는 이유는 dist가 **공유 가변 산출물**이라, 위 1/5 단계가
# 만든 dist를 4/5 단계가 복사하기까지 사이에 다른 빌드가 끼어들 수 있어서다.
#
# **포트가 붙은** 루프백 URL만 잡는다: react-router의 폴백 상수 `http://localhost`
# (포트 없음)가 정상 빌드에도 항상 들어있어 포트를 안 따지면 매번 오탐이 난다.
if grep -rEl --include='*.js' --include='*.html' \
     'https?://(localhost|127\.0\.0\.1):[0-9]+' "$BUNDLE/frontend-react/dist"; then
  echo "   위 파일에 절대 백엔드 URL이 박혀 있습니다 — 이대로 배포하면 API가 전부 CORS로 막힙니다."
  echo "   frontend-react/.env.production 을 확인하고, frontend-react/dist를 지운 뒤 다시 빌드하세요."
  exit 1
fi
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
