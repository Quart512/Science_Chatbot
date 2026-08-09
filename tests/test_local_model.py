"""
local_model.py 로컬 모델(Qwen-tuned) 선택 설치(08-09) — 네트워크 없이 계약만 검증한다.

여기서 지키려는 것은 두 가지다.
① **경로 계산이 MODELS_DIR을 따라간다** — 안 그러면 테스트가 진짜 models/ 폴더(986MB
   GGUF가 들어있는 곳)를 건드린다.
② **remove()가 우리가 받은 것만 지운다** — models/에는 사용자가 직접 넣어둔 파일이
   있을 수 있다(저자 기계에 실제로 있다).
"""
import platform

import pytest

import local_model


@pytest.fixture(autouse=True)
def models_dir(tmp_path, monkeypatch):
    """진짜 models/를 절대 안 건드리게 매 테스트마다 임시 폴더로 갈아끼운다."""
    monkeypatch.setattr(local_model, "MODELS_DIR", tmp_path / "models")
    local_model._status.update(
        {"state": "not_installed", "phase": "", "downloaded_bytes": 0, "total_bytes": 0, "error": None}
    )
    return tmp_path / "models"


def _fake_install(models_dir, *, binary_name="llama-server"):
    """설치가 끝난 모습을 흉내낸다 — 실제 릴리즈 압축의 배치(실행 파일 + 동반 dylib)."""
    llama = models_dir / "llama" / f"llama-{local_model.LLAMA_CPP_TAG}"
    llama.mkdir(parents=True)
    (llama / binary_name).write_text("#!/bin/sh\n", encoding="utf-8")
    (llama / "libllama-server-impl.dylib").write_bytes(b"\x00")
    (models_dir / local_model.QWEN_FILENAME).write_bytes(b"gguf")
    return llama / binary_name


def test_asset_name_covers_this_machine():
    """개발·배포 대상 플랫폼이 지원 목록에 있어야 한다. 없으면 UI가 '지원 안 함'을
    띄우는데, 그게 우리 기계에서 나오면 매핑이 틀린 것이다."""
    assert local_model.asset_name() is not None, (
        f"{platform.system()} {platform.machine()}가 _ASSETS에 없다"
    )


def test_asset_name_is_none_on_unsupported_platform(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Haiku")
    monkeypatch.setattr(platform, "machine", lambda: "m68k")
    assert local_model.asset_name() is None


def test_paths_follow_models_dir(models_dir):
    """경로가 모듈 로드 시점에 고정되면 MODELS_DIR 교체가 무력해진다(진짜 폴더 삭제 위험)."""
    assert local_model.gguf_path().parent == models_dir
    assert local_model.llama_dir().parent == models_dir


def test_server_binary_found_recursively_and_skips_libraries(models_dir):
    """압축 안 배치가 플랫폼마다 다르므로 재귀로 찾는다. 같이 들어있는 .dylib을
    실행 파일로 착각하면 안 된다."""
    expected = _fake_install(models_dir)
    assert local_model.server_binary() == expected


def test_server_binary_none_when_not_extracted(models_dir):
    assert local_model.server_binary() is None


def test_is_installed_requires_both_parts(models_dir):
    """GGUF만 있고 서버가 없으면 못 돌린다 — 설치됐다고 하면 안 된다."""
    models_dir.mkdir(parents=True)
    (models_dir / local_model.QWEN_FILENAME).write_bytes(b"gguf")
    assert local_model.is_installed() is False

    _fake_install(models_dir)
    assert local_model.is_installed() is True


def test_status_reports_installed_from_disk(models_dir):
    """지난 실행에서 받아뒀거나 사용자가 직접 지운 경우를 메모리 상태만 보고 판단하면 어긋난다."""
    assert local_model.get_status()["installed"] is False

    _fake_install(models_dir)
    status = local_model.get_status()
    assert status["installed"] is True
    assert status["state"] == "ready"  # 메모리엔 not_installed로 남아있어도 디스크가 이긴다


def test_install_is_a_noop_when_already_installed(models_dir, monkeypatch):
    """이미 있는데 또 받으면 1GB를 헛되이 다시 내려받는다."""
    _fake_install(models_dir)

    def explode(*a, **kw):
        raise AssertionError("이미 설치돼 있는데 다운로드를 시도했다")

    monkeypatch.setattr(local_model, "_download_and_extract_runtime", explode)
    monkeypatch.setattr(local_model, "hf_hub_download", explode)

    local_model.install()
    assert local_model.get_status()["state"] == "ready"


def test_remove_deletes_only_what_we_downloaded(models_dir):
    """models/에는 사용자가 직접 넣어둔 파일이 있을 수 있다 — 그건 남아야 한다."""
    _fake_install(models_dir)
    mine = models_dir / "내가-직접-넣은-모델.gguf"
    mine.write_bytes(b"user file")

    local_model.remove()

    assert not local_model.gguf_path().exists()
    assert not local_model.llama_dir().exists()
    assert mine.exists(), "사용자 파일까지 지웠다"
    assert models_dir.exists(), "models/ 디렉터리 자체를 지웠다"
    assert local_model.get_status()["state"] == "not_installed"


def test_install_skips_gguf_that_is_already_on_disk(models_dir, monkeypatch):
    """hf_hub_download는 같은 이름의 파일이 있어도 자기 메타데이터가 없으면 다시 받는다
    (08-09 실측). GGUF를 직접 넣어둔 기계에서 986MB를 헛되이 재다운로드하면 안 된다."""
    models_dir.mkdir(parents=True)
    (models_dir / local_model.QWEN_FILENAME).write_bytes("이미 있는 GGUF".encode())

    monkeypatch.setattr(local_model, "hf_hub_download", lambda **kw: pytest.fail("GGUF를 다시 받았다"))
    monkeypatch.setattr(local_model, "_download_and_extract_runtime",
                        lambda: _fake_install(models_dir))
    monkeypatch.setattr(local_model, "start_server", lambda: None)

    local_model.install()

    assert local_model.get_status()["state"] == "ready"


def test_start_server_does_nothing_when_not_installed(models_dir, monkeypatch):
    """설치 안 한 사용자가 대다수다 — 이 경로에서 프로세스를 띄우려 하면 안 된다."""
    monkeypatch.delenv("LOCAL_MODEL_URL", raising=False)
    monkeypatch.setattr(local_model.subprocess, "Popen", lambda *a, **kw: pytest.fail("Popen이 불렸다"))

    local_model.start_server()

    assert local_model.is_server_running() is False
    assert "LOCAL_MODEL_URL" not in local_model.os.environ


def test_start_server_respects_externally_configured_url(models_dir, monkeypatch):
    """docker-compose가 별도 llama-server 서비스를 가리키도록 설정해둔 경우
    (docker-compose.yml의 LOCAL_MODEL_URL) 우리가 덮어쓰면 그 구성이 조용히 깨진다."""
    _fake_install(models_dir)
    monkeypatch.setenv("LOCAL_MODEL_URL", "http://llama-server:8080/v1")
    monkeypatch.setattr(local_model.subprocess, "Popen", lambda *a, **kw: pytest.fail("Popen이 불렸다"))

    local_model.start_server()

    assert local_model.os.environ["LOCAL_MODEL_URL"] == "http://llama-server:8080/v1"


def test_remove_stops_the_server_first(models_dir, monkeypatch):
    """서버가 파일을 물고 있으면 Windows에서는 삭제가 실패하고, 다른 OS에서도
    죽은 서버가 계속 떠 있게 된다."""
    _fake_install(models_dir)
    calls: list = []
    monkeypatch.setattr(local_model, "stop_server", lambda: calls.append("stopped"))

    local_model.remove()

    assert calls == ["stopped"]
    assert not local_model.gguf_path().exists()


def test_progress_tqdm_tracks_only_the_byte_bar(models_dir):
    """embeddings.py와 같은 이유 — huggingface_hub가 tqdm_class를 파일 개수 바에도 쓴다."""
    byte_bar = local_model._ProgressTqdm(
        disable=True, name="t", desc="", total=0, initial=0, unit="B", unit_scale=True
    )
    byte_bar.update(4_096)
    file_bar = local_model._ProgressTqdm(disable=True, name="t", desc="", total=3)
    file_bar.update(1)

    assert local_model.get_status()["downloaded_bytes"] == 4_096


def test_progress_tqdm_records_total_from_constructor(models_dir):
    """총량을 안 받아두면 진행률이 2초 만에 100%를 찍고 1GB를 받는 내내 거기 멈춘다
    (08-09 실기에서 관측된 증상). hf_hub_download는 단일 파일이라 생성 시점에
    전체 크기를 kwargs로 넘겨준다."""
    local_model._ProgressTqdm(
        disable=True, name="t", desc="", total=986_047_936, initial=0, unit="B", unit_scale=True
    )

    status = local_model.get_status()
    assert status["total_bytes"] == 986_047_936
    assert status["downloaded_bytes"] == 0  # 아직 아무것도 안 받았다


def test_progress_tqdm_ignores_total_of_the_file_count_bar(models_dir):
    """파일 개수 바(unit이 "B"가 아님)의 total이 섞이면 바이트 총량이 오염된다."""
    local_model._ProgressTqdm(disable=True, name="t", desc="", total=8)

    assert local_model.get_status()["total_bytes"] == 0
