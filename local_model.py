"""로컬 모델(Qwen-tuned) 선택 설치 — API 키 없이도 앱이 도는 경로(08-09).

**왜 "선택" 설치인가.** CLAUDE.md §5는 무거운 의존성을 새로 끌어오지 말라고 하는데, 그
근거는 **다운로드 크기가 곧 첫 실행 경험**이라는 것이다(받다가 포기하면 앱을 아예 못 써봄).
그 제약이 겨냥하는 건 "써보기도 전에 강제로 받아야 하는 용량"이라, 원할 때만 받는 선택
다운로드는 거기 걸리지 않는다 — 배포판에는 안 싣고, 사용자가 설정 화면에서 누를 때만 받는다.

**받는 것 두 가지.** GGUF만으로는 안 된다. models.py의 Qwen 경로는 OpenAI 호환 서버에
HTTP로 붙는 클라이언트일 뿐이라(`_qwen_tuned_client`), 그 서버(llama.cpp의 `llama-server`)가
따로 있어야 한다.
  1. 파인튜닝 GGUF (986MB) — HuggingFace
  2. llama.cpp 실행 파일 + 공유 라이브러리 (11~18MB) — GitHub 릴리즈

**llama.cpp 버전을 고정하는 이유.** `latest`로 받으면 URL이 계속 바뀌고, 미래의 llama.cpp가
호환을 깨면 **이미 배포된 앱이 조용히 망가진다**. 올릴 때는 여기 상수 하나만 바꾸고 실기로
확인한 뒤 올린다.

**품질 경고는 UI가 진다.** 이 모델은 자체 평가에서 0.132점이다(같은 기준 claude-haiku
0.915). 받기 버튼 위에 그 사실을 명시하는 게 이 기능의 전제다 — 자세한 근거는
docs/README_09.md와 HF 모델 카드에 있다.
"""
import os
import platform
import shutil
import socket
import subprocess
import tarfile
import threading
import urllib.request
import zipfile
from pathlib import Path

from huggingface_hub import hf_hub_download
from huggingface_hub.utils import tqdm as hf_tqdm

MODELS_DIR = Path("models")  # data/·chroma_db/와 같은 CWD 기준 상대 경로

QWEN_REPO_ID = "Quart512/aisaac-qwen2.5-1.5b-gguf"
QWEN_FILENAME = "qwen_finetuned_Q4_K_M.gguf"

# 고정 버전(위 모듈 docstring 참고). 올릴 때는 실기 확인 후 이 값만 바꾼다.
LLAMA_CPP_TAG = "b10331"

# 플랫폼별 CPU 빌드. GPU 빌드(cuda·rocm·vulkan)는 일부러 안 쓴다 — 수백 MB로 커지는 데다
# 사용자 드라이버 환경에 따라 실패하는데, 1.5B 모델은 CPU로도 충분히 돈다.
_ASSETS = {
    ("Darwin", "arm64"): f"llama-{LLAMA_CPP_TAG}-bin-macos-arm64.tar.gz",
    ("Darwin", "x86_64"): f"llama-{LLAMA_CPP_TAG}-bin-macos-x64.tar.gz",
    ("Windows", "AMD64"): f"llama-{LLAMA_CPP_TAG}-bin-win-cpu-x64.zip",
    ("Windows", "ARM64"): f"llama-{LLAMA_CPP_TAG}-bin-win-cpu-arm64.zip",
    ("Linux", "x86_64"): f"llama-{LLAMA_CPP_TAG}-bin-ubuntu-x64.tar.gz",
    ("Linux", "aarch64"): f"llama-{LLAMA_CPP_TAG}-bin-ubuntu-arm64.tar.gz",
}

_status: dict = {
    "state": "not_installed",  # not_installed | downloading | ready | failed
    "phase": "",               # 사용자에게 보여줄 현재 단계 문구
    "downloaded_bytes": 0,
    "total_bytes": 0,
    "error": None,
}
_status_lock = threading.Lock()
_install_lock = threading.Lock()


def asset_name() -> str | None:
    """이 컴퓨터에 맞는 llama.cpp 릴리즈 파일 이름. 지원 목록에 없으면 None —
    "설치할 수 없음"을 조용히 성공으로 위장하지 않고 UI에 그대로 알린다."""
    return _ASSETS.get((platform.system(), platform.machine()))


# 경로는 상수가 아니라 함수다 — MODELS_DIR을 갈아끼우면(테스트) 전부 같이 따라와야
# 하는데, 모듈 로드 시점에 계산해두면 한쪽만 바뀌어 실제 파일을 건드리는 사고가 난다.
def gguf_path() -> Path:
    return MODELS_DIR / QWEN_FILENAME


def llama_dir() -> Path:
    return MODELS_DIR / "llama"


def server_binary() -> Path | None:
    """압축을 푼 뒤 llama-server 실행 파일을 **찾아서** 돌려준다.

    경로를 상수로 박지 않는 이유: 압축 안의 디렉터리 구조가 플랫폼마다 다르다(macOS는
    `llama-b10331/` 아래 평평하게, Windows 빌드는 다른 배치). 재귀 탐색이면 배치가
    바뀌어도 따라간다 — 릴리즈마다 레이아웃을 다시 확인할 일이 없다.
    """
    if not llama_dir().exists():
        return None
    for candidate in llama_dir().rglob("llama-server*"):
        # Windows는 .exe, 그 외는 확장자 없음. .dll/.dylib 같은 동반 파일은 제외한다
        # (libllama-server-impl.dylib이 실제로 같이 들어있다).
        if candidate.is_file() and candidate.suffix in ("", ".exe"):
            return candidate
    return None


def is_installed() -> bool:
    """둘 다 있어야 설치된 것이다 — GGUF만 있고 서버가 없으면 못 돌린다."""
    return gguf_path().exists() and server_binary() is not None


def get_status() -> dict:
    with _status_lock:
        status = dict(_status)
    # 설치 여부는 매번 디스크로 확인한다. 사용자가 파일을 직접 지웠거나 지난 실행에서
    # 받아둔 경우를 메모리 상태만 보고 판단하면 어긋난다.
    status["installed"] = is_installed()
    if status["state"] == "not_installed" and status["installed"]:
        status["state"] = "ready"
    status["supported"] = asset_name() is not None
    return status


def _set(**changes) -> None:
    with _status_lock:
        _status.update(changes)


def _add_downloaded(delta: int) -> None:
    with _status_lock:
        _status["downloaded_bytes"] += delta


class _ProgressTqdm(hf_tqdm):
    """hf_hub_download의 바이트 진행률을 _status로 흘린다.

    embeddings.py의 같은 이름 클래스와 구조가 같지만 **보고 대상이 다르다**(이쪽은
    local_model._status). 공용화하려면 "지금 어디로 보고할지"를 전역으로 들고 있어야
    하는데, 두 다운로드가 동시에 돌 수 있어서(첫 실행 중 로컬 모델 받기) 그 전역이
    곧 버그가 된다. 15줄 중복이 그 위험보다 싸다.

    disable=True면 tqdm이 self.unit을 설정하지 않고 __init__을 일찍 반환하므로 판별
    플래그를 super() 호출 전에 챙긴다(embeddings.py에 같은 주석).
    """

    def __init__(self, *args, **kwargs):
        self._tracks_bytes = kwargs.get("unit") == "B"
        super().__init__(*args, **kwargs)

    def update(self, n=1):
        if self._tracks_bytes and n:
            _add_downloaded(n)
        return super().update(n)


def _download_and_extract_runtime() -> None:
    """llama.cpp 릴리즈를 받아 models/llama/에 푼다.

    huggingface_hub 대신 표준 라이브러리 urllib을 쓴다 — requests는 pyproject.toml에
    없는 전이 의존성이라 언제 사라져도 이상하지 않다. 새 의존성을 안 늘리는 쪽이 맞다.
    """
    name = asset_name()
    if name is None:
        raise RuntimeError(
            f"지원하지 않는 환경입니다: {platform.system()} {platform.machine()}"
        )

    url = f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_CPP_TAG}/{name}"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    archive = MODELS_DIR / name

    with urllib.request.urlopen(url) as response:  # noqa: S310 — 위 상수로 만든 고정 URL
        total = int(response.headers.get("Content-Length") or 0)
        with _status_lock:
            _status["total_bytes"] += total
        with open(archive, "wb") as out:
            while chunk := response.read(1024 * 256):
                out.write(chunk)
                _add_downloaded(len(chunk))

    # 재설치를 대비해 이전 것을 지우고 푼다 — 옛 버전 dylib이 섞이면 원인 찾기 어려운
    # 로딩 실패가 난다.
    if llama_dir().exists():
        shutil.rmtree(llama_dir())
    llama_dir().mkdir(parents=True)

    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(llama_dir())
    else:
        with tarfile.open(archive) as tf:
            # filter="data"는 압축 안의 절대 경로·상위 경로(..)로 바깥 파일을 덮어쓰는
            # 공격을 막는다. 파이썬 3.14의 기본값이지만 의도를 남기려고 명시한다.
            tf.extractall(llama_dir(), filter="data")
    archive.unlink()

    binary = server_binary()
    if binary is None:
        raise RuntimeError("압축을 풀었지만 llama-server 실행 파일을 못 찾았습니다.")
    os.chmod(binary, 0o755)  # tar가 권한을 보존하지만 zip은 안 한다


def install() -> None:
    """런타임과 모델을 받는다. 이미 설치돼 있으면 아무 일도 안 한다."""
    with _install_lock:
        if is_installed():
            _set(state="ready", phase="", error=None)
            return
        try:
            _set(state="downloading", phase="실행 파일 받는 중", downloaded_bytes=0,
                 total_bytes=0, error=None)
            if server_binary() is None:
                _download_and_extract_runtime()

            # 파일이 이미 있으면 건너뛴다. hf_hub_download는 local_dir에 같은 이름의
            # 파일이 있어도 **자기 메타데이터(.cache/huggingface/download/)가 없으면 다시
            # 받는다**(08-09 실측 확인) — 저자처럼 GGUF를 직접 넣어둔 기계에서 "받기"를
            # 누르면 986MB를 헛되이 다시 받게 된다. 위 실행 파일 가드와 같은 이유·같은 모양.
            if not gguf_path().exists():
                _set(phase="모델 받는 중 (약 1GB)")
                # local_dir로 models/ 밑에 바로 떨어뜨린다 — HF 캐시(~/.cache)에 두면
                # 사용자가 "삭제"를 눌렀을 때 앱 폴더 밖을 건드려야 하고, 앱을 지워도
                # 1GB가 남는다. 이 파일은 앱에 속한 것이므로 앱 폴더 안에 둔다.
                hf_hub_download(
                    repo_id=QWEN_REPO_ID,
                    filename=QWEN_FILENAME,
                    local_dir=str(MODELS_DIR),
                    tqdm_class=_ProgressTqdm,
                )
        except Exception as e:
            _set(state="failed", phase="", error=f"{type(e).__name__}: {e}")
            raise
        _set(state="ready", phase="")
    # 락 밖에서 띄운다 — start_server()가 install()을 다시 부르지는 않지만,
    # 무거운 작업을 설치 락 안에 두면 "받기" 버튼의 재진입 가드가 필요 이상으로 오래 걸린다.
    start_server()


def install_in_background() -> None:
    """설정 화면의 "받기" 버튼이 부르는 진입점 — 요청을 붙잡아두지 않는다(1GB라
    HTTP 타임아웃에 걸린다). 진행 상황은 get_status()로 폴링한다."""
    if _install_lock.locked():
        return  # 이미 받는 중이면 두 번 시작하지 않는다
    threading.Thread(target=_install_safely, daemon=True, name="local-model-install").start()


def _install_safely() -> None:
    try:
        install()
    except Exception:
        pass  # 실패는 이미 _status에 남았다. 배경 스레드에서 예외를 올려봐야 갈 곳이 없다.


# ── llama-server 생명주기 ─────────────────────────────────────────────────────
# 설치돼 있으면 앱과 함께 띄우고 앱과 함께 끈다. "첫 Qwen 요청 때 켜기"도 검토했지만
# 그 요청이 모델 로딩(5~10초)을 통째로 기다려야 해서 첫 질문이 멈춘 것처럼 보인다.
# 대가는 상주 RAM 약 1.2GB인데, **받기를 명시적으로 선택한 사용자에게만** 해당하고
# 설정 화면의 삭제 버튼으로 되돌릴 수 있다.
_server_process = None
_server_lock = threading.Lock()


def _find_free_port() -> int:
    """실제로 bind해보고 그 포트를 쓴다 — "비어있나?" 물어본 뒤 나중에 서버가 잡는
    방식은 그 사이에 다른 프로세스가 끼어드는 레이스가 된다(run.sh가 8000번대에서
    같은 이유로 같은 방식을 쓴다)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))  # 0 = OS가 빈 포트를 골라줌
        return s.getsockname()[1]


def start_server() -> None:
    """설치돼 있으면 llama-server를 띄우고 models.py가 볼 주소를 환경변수에 심는다."""
    global _server_process
    with _server_lock:
        if _server_process is not None and _server_process.poll() is None:
            return
        if not is_installed():
            return
        # LOCAL_MODEL_URL이 이미 있으면 손대지 않는다 — docker-compose가 별도
        # llama-server 서비스를 가리키도록 설정해둔 경우다(docker-compose.yml). 우리가
        # 덮어쓰면 그 구성이 조용히 깨진다.
        if os.environ.get("LOCAL_MODEL_URL"):
            return

        binary = server_binary()
        port = _find_free_port()
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log = open(log_dir / "llama-server.log", "ab")

        _server_process = subprocess.Popen(
            [
                str(binary),
                "-m", str(gguf_path()),
                "--host", "127.0.0.1",  # 로컬 전용 — LAN에 노출할 이유가 없다
                "--port", str(port),
                "-c", "4096",           # models.py의 CONTEXT_BUDGET_CHARS가 전제하는 값
            ],
            stdout=log,
            stderr=log,
        )
        os.environ["LOCAL_MODEL_URL"] = f"http://127.0.0.1:{port}/v1"


def stop_server() -> None:
    global _server_process
    with _server_lock:
        if _server_process is None:
            return
        if _server_process.poll() is None:
            _server_process.terminate()
            try:
                _server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                _server_process.kill()  # 얌전히 안 죽으면 확실히 죽인다
        _server_process = None
        os.environ.pop("LOCAL_MODEL_URL", None)


def is_server_running() -> bool:
    return _server_process is not None and _server_process.poll() is None


def remove() -> None:
    """받은 것만 지운다 — models/ 디렉터리 자체나 사용자가 직접 넣어둔 다른 파일은
    건드리지 않는다."""
    # 서버가 파일을 물고 있는 상태에서 지우면 Windows에서는 삭제 자체가 실패하고,
    # 다른 OS에서도 죽은 서버가 계속 떠 있게 된다.
    stop_server()
    if gguf_path().exists():
        gguf_path().unlink()
    if llama_dir().exists():
        shutil.rmtree(llama_dir())
    # .cache는 hf_hub_download가 local_dir 안에 만드는 재개용 메타데이터다.
    cache = MODELS_DIR / ".cache"
    if cache.exists():
        shutil.rmtree(cache)
    _set(state="not_installed", phase="", downloaded_bytes=0, total_bytes=0, error=None)
