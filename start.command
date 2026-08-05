#!/bin/bash
# AIsaac 실행 스크립트(macOS, 08-05 Docker 패키징) — 더블클릭으로 실행.
# docker compose up → 헬스체크(/api/health) 폴링 → 준비되면 브라우저 자동 오픈.
# RoadMap "설치 앱의 UI 실행 방식" 설계 노트 참고.
set -e
cd "$(dirname "$0")"

echo "AIsaac을 시작합니다..."
echo

if ! command -v docker &> /dev/null; then
  echo "Docker를 찾을 수 없습니다."
  echo "https://www.docker.com/products/docker-desktop 에서 Docker Desktop을 먼저 설치해주세요."
  echo
  read -p "엔터를 누르면 창이 닫힙니다..." _
  exit 1
fi

if ! docker info &> /dev/null; then
  echo "Docker Desktop이 켜져 있지 않은 것 같습니다."
  echo "Docker Desktop 앱을 실행한 뒤 이 스크립트를 다시 실행해주세요."
  echo
  read -p "엔터를 누르면 창이 닫힙니다..." _
  exit 1
fi

if lsof -i :8000 -sTCP:LISTEN &> /dev/null; then
  echo "8000번 포트를 다른 프로그램이 이미 쓰고 있습니다."
  echo "그 프로그램을 종료한 뒤 이 스크립트를 다시 실행해주세요."
  echo
  read -p "엔터를 누르면 창이 닫힙니다..." _
  exit 1
fi

docker compose up -d

echo "서버가 준비될 때까지 기다리는 중입니다..."
echo "(처음 실행이면 이미지·AI 모델을 내려받느라 몇 분 정도 걸릴 수 있습니다 — 정상입니다)"
echo

# 최대 6분(180 * 2초) 대기 — bge-m3 첫 다운로드까지 포함해 실측 2~3분보다 넉넉히 잡음.
for i in $(seq 1 180); do
  if [ "$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null)" = "200" ]; then
    echo "준비 완료! 브라우저를 엽니다."
    open "http://localhost:8000"
    exit 0
  fi
  sleep 2
done

echo
echo "서버가 6분 안에 준비되지 않았습니다."
echo "터미널에서 'docker compose logs'를 실행해 상태를 확인해주세요."
echo
read -p "엔터를 누르면 창이 닫힙니다..." _
