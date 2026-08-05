@echo off
REM AIsaac 종료 스크립트(Windows, 08-05 Docker 패키징) — 더블클릭으로 실행.
REM 주의: macOS에서 개발 중이라 Windows에서 직접 실행해보지 못했다(stop.command와
REM 문법만 맞춤, 실제 검증 필요).
cd /d "%~dp0"

echo AIsaac을 종료합니다...
docker compose down
echo 종료됐습니다.
echo.
pause
