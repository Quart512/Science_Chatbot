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
# VITE_BACKEND_URL을 빈 문자열로 명시 오버라이드 — frontend-react/.env의 로컬 개발용
# 값(http://localhost:8000, Vite 5173 + 백엔드 8000 분리 실행 전제)이 그대로면 Vite가
# 빌드 시점에 이 값을 번들 JS에 박아버린다. 번들 앱은 http://127.0.0.1:8000에서
# 여는데 API는 http://localhost:8000으로 쏘게 돼 브라우저가 서로 다른 오리진으로 보고
# 실제 CORS 프리플라이트를 걸고(서버는 localhost:5173만 허용) 전부 막힌다(08-06 실기
# 테스트로 재현·확인). client.ts 주석이 말하는 "프로덕션은 같은 오리진, 빈 문자열
# 기본값" 의도를 빌드 시점에 강제한다.
(cd frontend-react && npm ci --silent && VITE_BACKEND_URL= npm run build)

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

echo "==> 5/5 조용한 .app 런처 생성"
# 손으로 만든 bash-as-.app(Info.plist + Contents/MacOS/<bash 스크립트>)은 08-06 실기
# 테스트에서 "응답하지 않습니다"로 거부당했다 — LaunchServices가 살아있는지 확인하는
# Apple Event ping에 답할 방법이 순수 bash 실행파일엔 없기 때문(실측으로 원인 확정,
# 아래 README_13.md §10 참고). 대신 osacompile로 AppleScript 런처를 컴파일한다 —
# 이건 macOS 기본 OSA 런타임 위에서 도는 진짜 Cocoa 앱이라 그 ping에 정상 응답한다.
# 실제 작업(run.sh)은 여전히 번들 루트에 별도 파일로 두고 배경으로 던지기만 한다.
APP="$BUNDLE/AIsaac.app"
rm -rf "$APP"

cat > "$BUNDLE/run.sh" <<'LAUNCHER'
#!/bin/bash
# AIsaac 실제 작업 — AIsaac.app(osacompile 런처)이 백그라운드로 던지는 스크립트.
# LaunchServices의 응답성 감시 대상이 아니라서 원하는 만큼 오래 떠 있어도 된다.
set -uo pipefail

cd "$(dirname "$0")"
mkdir -p logs

# lsof로 먼저 "비어있나?" 물어보고 나중에 uvicorn이 bind하는 방식은 그 사이에 다른
# 프로세스가 끼어들 수 있는 확인-후-사용 레이스(TOCTOU)라 8000이 막혀도 자동으로
# 복구가 안 됐다(08-06 논의). 대신 실제 bind를 직접 시도해 다음 포트로 넘어간다 —
# 소켓을 열어보는 것 자체가 곧 "비어있는지 확인"이라 별도 사전 체크와 결과가 어긋날
# 일이 없다. 8000~8049 안에서 못 찾으면(사실상 불가능한 상황) 빈 문자열을 낸다.
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
  osascript -e 'display alert "AIsaac" message "8000~8049번 포트를 전부 다른 프로그램이 쓰고 있어 실행할 수 없습니다." as critical' &> /dev/null
  exit 1
fi

# --host 127.0.0.1 — Docker판은 컨테이너 네트워킹 때문에 0.0.0.0이 필수였지만, 번들은
# 호스트에서 직접 도니 LAN에 노출할 이유가 없다. 터미널이 없으므로 출력은 로그 파일로.
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
  osascript -e 'display alert "AIsaac" message "서버가 응답하지 않습니다. logs/server.log 를 확인해주세요." as critical' &> /dev/null
  kill "$SERVER_PID" 2>/dev/null
  exit 1
fi

# 격리 프로필 — 고정 경로를 쓴다(재실행해도 로그인 세션이 유지됨). 같은 프로필로
# 두 번째 실행이 걸리면 Chrome 자체 싱글턴 락이 새 창만 기존 프로세스에 얹고 반환하는
# 걸 실측으로 확인했다(08-06) — 그래서 아래 "창이 살아있는지" 판정은 프로세스 종료
# 대기(wait)가 아니라 AppleScript로 창 존재 자체를 직접 물어본다.
PROFILE_DIR="$HOME/Library/Application Support/AIsaac/chrome-profile"
mkdir -p "$PROFILE_DIR"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
EDGE="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
APP_URL="http://127.0.0.1:$PORT"

BROWSER_APP=""
if [ -x "$CHROME" ]; then
  BROWSER_APP="Google Chrome"
  BROWSER_BIN="$CHROME"
elif [ -x "$EDGE" ]; then
  BROWSER_APP="Microsoft Edge"
  BROWSER_BIN="$EDGE"
fi

if [ -z "$BROWSER_APP" ]; then
  # Chrome/Edge 둘 다 없으면 일반 브라우저 탭으로 폴백 — 앱모드도, 창 종료 감지도 못
  # 하므로 서버는 계속 백그라운드에 남는다(다음 실행 시 포트 점유로 사용자가 알아챔).
  open "$APP_URL"
  disown "$SERVER_PID" 2>/dev/null
  exit 0
fi

"$BROWSER_BIN" --app="$APP_URL" --user-data-dir="$PROFILE_DIR" \
  --no-first-run --no-default-browser-check >> logs/browser.log 2>&1 &

# 창이 실제로 열릴 시간을 준 뒤, 우리 URL을 가진 창이 남아있는 동안 폴링한다.
sleep 3
while true; do
  count=$(osascript -e "tell application \"$BROWSER_APP\" to count (windows whose (URL of active tab contains \"127.0.0.1:$PORT\"))" 2>/dev/null)
  [ "${count:-0}" = "0" ] && break
  sleep 3
done

kill "$SERVER_PID" 2>/dev/null
LAUNCHER
chmod +x "$BUNDLE/run.sh"

# osacompile 런처 — 진짜 하는 일은 "mkdir -p logs && nohup run.sh &"뿐이다. do shell
# script는 백그라운드로 던진 뒤 즉시 반환하므로 이 앱 자신은 순식간에 끝나고, 그 사이
# LaunchServices의 응답성 체크에 정상적으로 답한다(applet 바이너리가 원래 그렇게 동작).
osacompile -o "$APP" <<'APPLESCRIPT'
on run
	set appPosixPath to POSIX path of (path to me)
	set bundleRoot to do shell script "dirname " & quoted form of (text 1 thru -2 of appPosixPath)
	do shell script "mkdir -p " & quoted form of (bundleRoot & "/logs") & ¬
		" && nohup " & quoted form of (bundleRoot & "/run.sh") & ¬
		" >> " & quoted form of (bundleRoot & "/logs/launcher.log") & " 2>&1 & disown"
end run
APPLESCRIPT

cat > "$BUNDLE/README.txt" <<'READMEEOF'
AIsaac — 물리 연구 어시스턴트

중요: 이 AIsaac 폴더는 바탕화면·문서·다운로드 폴더 "안"에 두지 마세요.
macOS 보안 정책 때문에 그 세 폴더 밑에서는 첫 실행이 멈추거나 실패할 수
있습니다. 압축을 풀었다면 이 폴더를 사용자 폴더 바로 밑이나 별도 폴더로
옮긴 뒤 실행하세요(예: 다운로드 폴더에서 사용자 홈 폴더로 드래그).

실행: AIsaac.app 을 더블클릭하세요(Terminal 창이 뜨지 않습니다).
종료: 열린 앱 창을 닫으면 서버도 함께 종료됩니다.
로그: 문제가 있으면 logs/server.log 를 확인하세요.

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
