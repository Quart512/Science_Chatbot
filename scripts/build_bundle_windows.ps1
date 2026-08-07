# AIsaac portable 번들 빌더 (Windows) — 08-06.
#
# scripts/build_bundle_macos.sh와 같은 접근(독립 실행 파이썬 + 설치된 패키지를 폴더째
# 담기 — RoadMap 설계 노트 "Electron 검토" 참고)을 Windows로 옮긴 것. 레이아웃도 macOS
# 번들과 동일하게 저장소 루트를 그대로 흉내낸다(data/·chroma_db가 CWD 기준 상대경로).
#
# macOS와 다른 지점 두 가지(둘 다 실기 Windows에서 아직 검증 안 됨, README 참고):
# ① 콘솔 숨기기 — macOS는 osacompile(진짜 Cocoa 앱)이 필요했지만 Windows는 훨씬 단순하다.
#    .vbs로 감싼 PowerShell 호출은 WindowStyle=0(숨김)으로 콘솔 자체가 안 뜨고, 서버는
#    console 서브시스템 python.exe 대신 GUI 서브시스템 pythonw.exe로 띄우면 그 프로세스도
#    콘솔이 안 뜬다(python-build-standalone Windows 빌드에 기본 포함).
# ② 브라우저 창 종료 감지 — macOS는 osascript로 "창이 남아있는지" 직접 물어봤다(고정
#    프로필 재사용 시 Chrome 싱글턴 락 때문에 프로세스 wait가 못 미더워서). Windows엔
#    그런 IPC가 기본으로 없어서, 대신 **매 실행마다 새 임시 프로필**을 써서 싱글턴 충돌
#    자체를 없앤다 — 그러면 Start-Process가 돌려주는 프로세스 핸들을 그대로 Wait-Process
#    해도 안전하다(로그인 세션이 재실행마다 안 남는 대신, 실기 검증 없이도 신뢰할 수
#    있는 더 단순한 경로를 택함 — 08-06 판단).

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $RepoRoot "build"
$Bundle = Join-Path $BuildRoot "AIsaac"

Set-Location $RepoRoot

Write-Host "==> 이전 빌드 정리"
if (Test-Path $Bundle) { Remove-Item -Recurse -Force $Bundle }
New-Item -ItemType Directory -Force -Path (Join-Path $Bundle "runtime") | Out-Null

Write-Host "==> 1/5 프론트엔드 빌드"
# VITE_BACKEND_URL을 빈 문자열로 명시 오버라이드 — frontend-react/.env의 로컬 개발용
# 값(http://localhost:8000)이 그대로면 Vite가 빌드 시점에 번들 JS에 박아버려 프로덕션
# 빌드가 127.0.0.1과 localhost를 다른 오리진으로 취급하는 CORS 버그가 난다(08-06,
# macOS 번들 실기 테스트로 발견 — RoadMap "포터블 번들 실기 테스트로 발견한 크래시" 참고).
Push-Location (Join-Path $RepoRoot "frontend-react")
try {
    npm ci --silent
    if ($LASTEXITCODE -ne 0) { throw "npm ci 실패" }
    $env:VITE_BACKEND_URL = ""
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build 실패" }
} finally {
    Remove-Item Env:\VITE_BACKEND_URL -ErrorAction SilentlyContinue
    Pop-Location
}

Write-Host "==> 2/5 프로덕션 의존성 설치 (--no-dev)"
# UV_PROJECT_ENVIRONMENT로 대상 venv를 따로 지정 — 안 하면 프로젝트 .venv를 --no-dev로
# 덮어써서 개발자의 pytest 등이 사라진다(macOS 스크립트와 같은 이유).
$BuildVenv = Join-Path $BuildRoot "venv"
if (Test-Path $BuildVenv) { Remove-Item -Recurse -Force $BuildVenv }
$env:UV_PROJECT_ENVIRONMENT = $BuildVenv
try {
    uv sync --no-dev --frozen --quiet
    if ($LASTEXITCODE -ne 0) { throw "uv sync 실패" }
} finally {
    Remove-Item Env:\UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
}

$SitePackages = Get-ChildItem -Path (Join-Path $BuildVenv "Lib") -Directory -Filter "site-packages" -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $SitePackages) { $SitePackages = Join-Path $BuildVenv "Lib\site-packages" }
Copy-Item -Recurse -Force $SitePackages.FullName (Join-Path $Bundle "runtime\lib")

Write-Host "==> 3/5 독립 실행 파이썬 복사"
# uv가 관리하는 python-build-standalone 배포본을 그대로 쓴다(venv가 아니라 원본
# 인터프리터 — venv는 절대경로가 박혀 다른 기계로 못 옮긴다, macOS 스크립트와 같은 이유).
# JSON으로 조회해 이 uv가 실제로 어디에 설치했는지 직접 물어본다(경로를 하드코딩 안 함 —
# uv 버전·환경마다 저장 위치가 달라질 수 있어서).
$PythonListJson = uv python list --only-installed --output-format json | ConvertFrom-Json
$PythonEntry = $PythonListJson | Where-Object {
    $_.version -like "3.14*" -and $_.path -like "*\uv\python\*"
} | Select-Object -First 1

if (-not $PythonEntry) {
    Write-Error "독립 실행 파이썬(3.14)을 못 찾았습니다. 'uv python install 3.14'를 먼저 실행하세요."
    exit 1
}

# 보고된 path는 보통 .../cpython-3.14...-windows-.../python.exe(또는 install\python.exe)를
# 직접 가리킨다 — 그 실행파일이 들어있는 디렉터리 전체를 복사 대상으로 삼는다(macOS의
# ".../bin/python3.14" -> ".../bin" 상위 디렉터리 자르기와 같은 아이디어, 다만 Windows
# 레이아웃엔 bin/이 없어 실행파일이 있는 폴더 자체가 곧 배포 루트).
$PythonExeSrc = $PythonEntry.path
$PythonSrcDir = Split-Path -Parent $PythonExeSrc
Copy-Item -Recurse -Force $PythonSrcDir (Join-Path $Bundle "runtime\python")

Write-Host "==> 4/5 앱 소스 복사"
# macOS 스크립트와 완전히 같은 화이트리스트 — 배포판에 들어갈 것만 명시(블랙리스트로
# 하면 새 파일이 조용히 딸려 들어감). ingest.py는 일부러 뺀다(import만으로
# Chroma.from_texts가 실행되는 일회성 스크립트).
$Items = @(
    "main.py", "graph.py", "models.py", "orchestrator.py", "retrieval.py", "embeddings.py",
    "tool.py", "interests.py", "knowledge_notes.py", "api_keys.py", "chat_sessions.py",
    "wikipedia_api.py",
    "arxiv_api.py", "paper_catalog.py", "paper_search.py", "paper_screening.py",
    "paper_recommend.py", "reference_recommender.py", "research_workflow.py",
    "research_sessions.py", "research_branches.py", "research_notes.py",
    "equipment.py", "library_order.py", "paper"
)
foreach ($item in $Items) {
    $src = Join-Path $RepoRoot $item
    if (-not (Test-Path $src)) {
        Write-Error "빠진 파일: $item"
        exit 1
    }
    Copy-Item -Recurse -Force $src (Join-Path $Bundle $item)
}
New-Item -ItemType Directory -Force -Path (Join-Path $Bundle "frontend-react") | Out-Null
Copy-Item -Recurse -Force (Join-Path $RepoRoot "frontend-react\dist") (Join-Path $Bundle "frontend-react\dist")

Write-Host "==> 5/5 조용한 런처 생성"
# run.ps1 — 실제 작업(서버 기동·헬스체크·브라우저·창 종료 감지 후 서버 종료). AIsaac.vbs가
# 이걸 숨김창으로 호출만 하고 빠진다(macOS의 osacompile 앱 -> run.sh 분리와 같은 구조 —
# 다만 Windows는 LaunchServices 응답성 문제가 없어서 분리 자체는 필수는 아니고, 로그·
# 예외 처리를 한 파일에 모아두려는 목적이 더 크다).
$RunPs1 = @'
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

$tcp = New-Object System.Net.Sockets.TcpClient
try {
    $tcp.Connect("127.0.0.1", 8000)
    $tcp.Close()
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show("8000번 포트를 다른 프로그램이 이미 쓰고 있습니다. 그 프로그램을 종료한 뒤 다시 실행해주세요.", "AIsaac") | Out-Null
    exit 1
} catch {
    # 연결 실패 = 포트가 비어있음(정상 경로)
}

# pythonw.exe(GUI 서브시스템, 콘솔 없음)를 우선 쓰고 없으면 python.exe를 숨김 스타일로.
$PythonwPath = Join-Path "runtime\python" "pythonw.exe"
$PythonPath = Join-Path "runtime\python" "python.exe"
$env:PYTHONPATH = "runtime\lib"

if (Test-Path $PythonwPath) {
    $serverProc = Start-Process -FilePath $PythonwPath `
        -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000" `
        -RedirectStandardOutput "logs\server.log" -RedirectStandardError "logs\server.err.log" `
        -PassThru
} else {
    $serverProc = Start-Process -FilePath $PythonPath `
        -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WindowStyle Hidden `
        -RedirectStandardOutput "logs\server.log" -RedirectStandardError "logs\server.err.log" `
        -PassThru
}

$ready = $false
for ($i = 0; $i -lt 180; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show("서버가 응답하지 않습니다. logs\server.log 를 확인해주세요.", "AIsaac") | Out-Null
    Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

# 매 실행마다 새 임시 프로필 — Chrome/Edge의 프로필 싱글턴 락(같은 프로필로 재실행하면
# 새 창만 기존 프로세스에 얹고 새 프로세스는 곧장 종료됨, macOS에서 실측 확인된 동작이라
# Windows도 같은 Chromium 엔진이라 동일할 것으로 봄)을 피하려고 고정 프로필 대신 매번
# 새로 만든다 — Wait-Process로 반환된 프로세스를 그대로 신뢰할 수 있게 됨(로그인 세션이
# 재실행마다 안 남는 게 대가지만, 앱모드 창 하나 띄우는 용도라 크게 아쉽지 않다는 판단).
$AppUrl = "http://127.0.0.1:8000"
$Profile = Join-Path $env:TEMP ("AIsaac-chrome-" + [guid]::NewGuid().ToString())

$ChromePaths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
)
$EdgePaths = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)
$BrowserBin = ($ChromePaths + $EdgePaths) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $BrowserBin) {
    Start-Process $AppUrl
    exit 0
}

$browserProc = Start-Process -FilePath $BrowserBin `
    -ArgumentList "--app=$AppUrl", "--user-data-dir=$Profile", "--no-first-run", "--no-default-browser-check" `
    -PassThru

Wait-Process -Id $browserProc.Id -ErrorAction SilentlyContinue

Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $Profile -ErrorAction SilentlyContinue
'@
Set-Content -Path (Join-Path $Bundle "run.ps1") -Value $RunPs1 -Encoding UTF8

# AIsaac.vbs — 더블클릭 진입점. WindowStyle=0(숨김)으로 PowerShell 자체도 콘솔 없이 뜬다.
$LauncherVbs = @'
Set objShell = CreateObject("WScript.Shell")
scriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
objShell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & scriptDir & "run.ps1""", 0, False
'@
Set-Content -Path (Join-Path $Bundle "AIsaac.vbs") -Value $LauncherVbs -Encoding ASCII

$ReadmeTxt = @'
AIsaac - 물리 연구 어시스턴트

중요: 이 AIsaac 폴더는 바탕화면 다운로드 폴더 안에 두지 말고, 사용자 폴더
바로 밑이나 별도 폴더로 옮긴 뒤 실행하세요.

실행: AIsaac.vbs 를 더블클릭하세요(콘솔 창이 뜨지 않습니다).
종료: 열린 브라우저 창을 닫으면 서버도 함께 종료됩니다.
로그: 문제가 있으면 logs\server.log 를 확인하세요.

처음 실행할 때는 AI 임베딩 모델(약 2GB)을 내려받으므로 몇 분 걸립니다.
두 번째부터는 바로 뜹니다.

AI 모델 API 키는 앱 안의 "설정" 화면에서 입력합니다.
데이터(논문, 노트, 대화 기록)는 이 폴더의 chroma_db\ 와 data\ 에 저장됩니다.
'@
Set-Content -Path (Join-Path $Bundle "README.txt") -Value $ReadmeTxt -Encoding UTF8

Write-Host "==> 검증: 번들이 스스로 import되는지"
# 화이트리스트가 틀리면 사용자가 실행했을 때야 ModuleNotFoundError로 드러난다(macOS
# 빌드에서 실제로 이렇게 발견된 전례 — chat_sessions.py·wikipedia_api.py 누락). 빌드가
# 끝나기 전에 번들 자신의 파이썬으로 main을 import해보고, 실패하면 빌드를 실패시킨다.
Push-Location $Bundle
try {
    $env:PYTHONPATH = "runtime\lib"
    & ".\runtime\python\python.exe" -c "import main"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "번들 import 실패 - 위 오류를 보고 화이트리스트를 고치세요."
        exit 1
    }
    Write-Host "   OK"
} finally {
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    Pop-Location
}

Write-Host "==> 검증: 프론트엔드가 같은 오리진을 쓰는지"
# 위 `import main`이 백엔드 화이트리스트에 대해 하는 일을 프론트엔드 환경변수에 대해
# 똑같이 한다. 08-07에 http://localhost:8000이 박힌 dist가 번들에 들어가 API 호출이
# 전부 CORS로 막힌 적이 있다(macOS에서 실제로 겪음) — 화면(정적 자산)은 멀쩡히 떠서
# 사용자 눈에는 원인 불명의 "백엔드 연결 실패"로만 보였다.
#
# 정상 경로는 frontend-react/.env.production이 이미 막아뒀다(어떤 mode로 빌드하든 빈
# 값). 그럼에도 여기서 또 보는 이유는 dist가 **공유 가변 산출물**이라, 프론트 빌드
# 단계가 만든 dist를 복사 단계가 가져가기까지 사이에 다른 빌드가 끼어들 수 있어서다.
#
# **포트가 붙은** 루프백 URL만 잡는다: react-router의 폴백 상수 `http://localhost`
# (포트 없음)가 정상 빌드에도 항상 들어있어 포트를 안 따지면 매번 오탐이 난다.
#
# Get-ChildItem은 -Recurse와 -Include를 같이 쓸 때 경로 형태에 따라 조용히 아무것도
# 안 잡는 함정이 있어, 확장자 필터를 Where-Object로 명시한다(검사가 조용히 통과하면
# 검사가 없는 것보다 나쁘다). 이 스크립트 전체가 그렇듯 실기 Windows 검증은 아직 안 됨.
$DistRoot = Join-Path $Bundle "frontend-react\dist"
$DistFiles = Get-ChildItem -Path $DistRoot -Recurse -File |
    Where-Object { $_.Extension -in '.js', '.html' }
$Baked = $DistFiles | Select-String -Pattern 'https?://(localhost|127\.0\.0\.1):[0-9]+'
if ($Baked) {
    $Baked | ForEach-Object { Write-Host ("   " + $_.Path) }
    Write-Error "위 파일에 절대 백엔드 URL이 박혀 있습니다 - 이대로 배포하면 API가 전부 CORS로 막힙니다. frontend-react\.env.production 을 확인하고 frontend-react\dist를 지운 뒤 다시 빌드하세요."
    exit 1
}
Write-Host "   OK"

Write-Host ""
Write-Host "완료: $Bundle"
$size = (Get-ChildItem -Recurse $Bundle | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host ("{0:N0} MB" -f $size)
