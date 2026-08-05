#!/bin/bash
# AIsaac 종료 스크립트(macOS, 08-05 Docker 패키징) — 더블클릭으로 실행.
# 브라우저 탭을 닫아도 컨테이너는 백그라운드에서 계속 살아있으므로(RoadMap "착수하면
# 바로 걸릴 것" 참고) 별도 종료 스크립트가 필요하다.
cd "$(dirname "$0")"

echo "AIsaac을 종료합니다..."
docker compose down
echo "종료됐습니다."
echo
read -p "엔터를 누르면 창이 닫힙니다..." _
