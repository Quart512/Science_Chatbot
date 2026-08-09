#!/bin/bash
# AIsaac 설치 스크립트 (macOS · Linux) — 08-09.
#
# 사용법:
#   curl -fsSL https://raw.githubusercontent.com/Quart512/AIsaac/main/scripts/install.sh | bash
#
# **왜 이게 필요한가 — 브라우저 다운로드의 구조적 문제.**
# macOS의 격리 딱지(com.apple.quarantine)는 OS가 붙이는 게 아니라 **내려받은 프로그램이**
# 붙인다. Safari·Chrome은 붙이고 curl은 안 붙인다. 브라우저로 zip을 받으면 압축을 풀 때
# 그 딱지가 **풀려나온 파일 전부에** 복사되고, 그때부터 이런 일이 벌어진다:
#   - AIsaac.app이 Gatekeeper에 막혀 "시스템 설정 → 개인정보 보호 및 보안 → 그래도 열기"
#     3단계를 사람이 통과시켜야 한다.
#   - 그 승인은 **그 위치의 그 파일**에 기록되므로 폴더를 옮기면 무효가 된다.
#   - run.sh가 나머지 파일의 딱지를 스스로 지우게 해뒀지만(08-09), 그 코드는 .app이
#     실행돼야 돌기 때문에 승인이 막히면 자가 치유가 시작조차 못 한다(닭-달걀).
#     게다가 그 경우 로그가 하나도 안 남아 사용자는 원인을 알 방법이 없다.
# curl로 받으면 **딱지가 애초에 안 붙어서** 위 문제가 통째로 사라진다(08-09 실측 확인:
# curl로 받아 푼 파일의 격리 속성 0개).
#
# **설치 위치를 사용자에게 맡기지 않는 이유.**
# 바탕화면·문서·다운로드 폴더 밑에서는 macOS 개인정보 보호 정책 때문에 첫 실행이 실패할
# 수 있어서 지금까지 "그 세 폴더에 두지 마세요"라고 안내해왔는데, 그 안내가 안 지켜지는
# 게 실제 실패 원인이었다. 여기서는 $HOME/AIsaac으로 **스크립트가 정한다** — 사용자가
# 어느 폴더에서 명령을 실행하든 결과가 같다. 지켜야 할 규칙을 없애는 쪽이 규칙을 잘
# 안내하는 것보다 낫다.
set -euo pipefail

REPO="Quart512/AIsaac"
INSTALL_DIR="$HOME/AIsaac"
# 사용자가 만든 것들 — 재설치·업그레이드 때 절대 날리면 안 된다. 번들에도 같은 이름의
# 디렉터리가 들어있어서(빌드 중 import가 만든 빈 chroma_db 등) 그냥 덮어쓰면 조용히 사라진다.
PRESERVE=(data chroma_db library models)

say() { printf '%s\n' "$*"; }
die() { printf '오류: %s\n' "$*" >&2; exit 1; }

# ── 1. 플랫폼 판별 ────────────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS/$ARCH" in
  Darwin/arm64)  ASSET="AIsaac-macos.zip" ;;
  Linux/x86_64)  ASSET="AIsaac-linux.zip" ;;
  Darwin/x86_64)
    die "Intel Mac은 이 설치 방식을 쓸 수 없습니다.
     내부적으로 쓰는 라이브러리가 Intel Mac용 배포본을 더 이상 만들지 않아 생긴 제약입니다.
     Docker 버전을 받아주세요: https://github.com/$REPO/releases/latest"
    ;;
  *)
    die "지원하지 않는 환경입니다: $OS $ARCH
     Docker 버전을 받아주세요: https://github.com/$REPO/releases/latest"
    ;;
esac

command -v curl >/dev/null || die "curl이 필요합니다."
command -v unzip >/dev/null || die "unzip이 필요합니다."

say "==> AIsaac 설치 ($OS $ARCH)"
say "    설치 위치: $INSTALL_DIR"

# ── 2. 내려받기 ──────────────────────────────────────────────────────────────
# releases/latest/download/<파일>은 GitHub이 항상 최신 릴리즈로 리다이렉트해준다 —
# 버전 번호를 스크립트에 박지 않아도 된다(landing/lib/download.ts와 같은 방식).
URL="https://github.com/$REPO/releases/latest/download/$ASSET"
TMP="$(mktemp -d)"
# 중간에 실패하든 성공하든 임시 폴더는 반드시 치운다(수백 MB짜리라 남으면 곤란).
trap 'rm -rf "$TMP"' EXIT

say "==> 내려받는 중 (약 250MB)"
curl -fL --progress-bar -o "$TMP/$ASSET" "$URL" \
  || die "다운로드 실패 — 인터넷 연결을 확인해주세요."

say "==> 압축 푸는 중"
unzip -q "$TMP/$ASSET" -d "$TMP/extracted"
NEW="$TMP/extracted/AIsaac"
[ -d "$NEW" ] || die "압축 내용이 예상과 다릅니다(AIsaac 폴더가 없음)."

# ── 3. 기존 설치가 있으면 사용자 데이터를 새 버전으로 옮긴다 ──────────────────
if [ -d "$INSTALL_DIR" ]; then
  say "==> 기존 설치 발견 — 데이터(논문·노트·대화 기록·받아둔 모델)를 그대로 옮깁니다"
  for item in "${PRESERVE[@]}"; do
    if [ -e "$INSTALL_DIR/$item" ]; then
      rm -rf "$NEW/$item"            # 번들에 들어있는 빈 디렉터리를 치우고
      mv "$INSTALL_DIR/$item" "$NEW/" # 사용자 것을 그 자리에 넣는다
    fi
  done
fi

# ── 4. 자리 바꾸기 ───────────────────────────────────────────────────────────
# 새 버전을 완성한 뒤 마지막에 한 번만 바꾼다 — 앞 단계에서 실패해도 기존 설치가
# 멀쩡히 남아있게 하려는 것이다(먼저 지우고 받으면 실패 시 아무것도 안 남는다).
if [ -d "$INSTALL_DIR" ]; then
  OLD="$INSTALL_DIR.old-$$"
  mv "$INSTALL_DIR" "$OLD"
fi
mv "$NEW" "$INSTALL_DIR"
[ -n "${OLD:-}" ] && rm -rf "$OLD"

chmod +x "$INSTALL_DIR/run.sh" 2>/dev/null || true

say ""
say "==> 설치 완료: $INSTALL_DIR"
say ""
if [ "$OS" = "Darwin" ]; then
  say "실행: Finder에서 $INSTALL_DIR 폴더의 AIsaac.app 을 더블클릭하세요."
  say "      (이 방식으로 설치하면 '확인되지 않은 개발자' 경고가 뜨지 않습니다)"
  # 바로 찾아갈 수 있게 Finder를 열어준다. 실패해도 설치 자체는 끝난 상태다.
  open "$INSTALL_DIR" 2>/dev/null || true
else
  say "실행: $INSTALL_DIR/run.sh"
fi
say ""
say "처음 실행하면 검색용 AI 모델(약 2GB)을 내려받습니다 — 진행률이 화면 아래에 표시되고,"
say "그동안 설정 화면에서 API 키를 넣어두면 됩니다."
