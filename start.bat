@echo off
REM AIsaac 실행 스크립트(Windows, 08-05 Docker 패키징) — 더블클릭으로 실행.
REM docker compose up -> 헬스체크(/api/health) 폴링 -> 준비되면 브라우저 자동 오픈.
REM RoadMap "설치 앱의 UI 실행 방식" 설계 노트 참고.
REM 주의: 이 스크립트는 macOS에서 개발 중이라 Windows에서 직접 실행해보지 못했다 —
REM start.command와 문법만 맞춰 작성함(실제 검증 필요).
cd /d "%~dp0"

echo AIsaac을 시작합니다...
echo.

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker를 찾을 수 없습니다.
  echo https://www.docker.com/products/docker-desktop 에서 Docker Desktop을 먼저 설치해주세요.
  echo.
  pause
  exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
  echo Docker Desktop이 켜져 있지 않은 것 같습니다.
  echo Docker Desktop 앱을 실행한 뒤 이 스크립트를 다시 실행해주세요.
  echo.
  pause
  exit /b 1
)

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>nul
if not errorlevel 1 (
  echo 8000번 포트를 다른 프로그램이 이미 쓰고 있습니다.
  echo 그 프로그램을 종료한 뒤 이 스크립트를 다시 실행해주세요.
  echo.
  pause
  exit /b 1
)

docker compose up -d

echo 서버가 준비될 때까지 기다리는 중입니다...
echo (처음 실행이면 이미지·AI 모델을 내려받느라 몇 분 정도 걸릴 수 있습니다 — 정상입니다)
echo.

REM 최대 6분(180 * 2초) 대기 — bge-m3 첫 다운로드까지 포함해 실측 2~3분보다 넉넉히 잡음.
set count=0

:waitloop
for /f %%s in ('curl -s -o nul -w "%%{http_code}" http://localhost:8000/api/health 2^>nul') do set status=%%s
if "%status%"=="200" (
  echo 준비 완료! 브라우저를 엽니다.
  start http://localhost:8000
  exit /b 0
)
set /a count+=1
if %count% geq 180 goto timeout
timeout /t 2 >nul
goto waitloop

:timeout
echo.
echo 서버가 6분 안에 준비되지 않았습니다.
echo 명령 프롬프트에서 'docker compose logs'를 실행해 상태를 확인해주세요.
echo.
pause
