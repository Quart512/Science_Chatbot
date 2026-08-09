"""
embeddings.py 지연 로딩(08-09) — 네트워크·실제 모델 없이 계약만 검증한다.

여기서 지키려는 계약은 하나다: **무거운 준비가 import·생성 시점에 일어나지 않는다.**
이게 깨지면 `import retrieval` → `import main` 경로가 다시 2.1GB 다운로드를 기다리게
되고, 첫 실행이 몇 분간 빈 화면 + run.sh 360초 타임아웃 실패로 되돌아간다.
"""
import threading

import pytest

import embeddings


@pytest.fixture(autouse=True)
def reset_module_state():
    """모듈 전역(_model·_status)을 쓰는 코드라 테스트끼리 상태가 샌다. 각 테스트 전후로
    초기화해 실행 순서에 무관하게 만든다."""
    embeddings._model = None
    embeddings._status.update(
        {"state": "idle", "downloaded_bytes": 0, "total_bytes": 0, "error": None}
    )
    yield
    embeddings._model = None
    embeddings._status.update(
        {"state": "idle", "downloaded_bytes": 0, "total_bytes": 0, "error": None}
    )


def test_constructing_adapter_does_not_load_model(monkeypatch):
    """생성은 공짜여야 한다 — retrieval.py가 모듈 최상단에서 이걸 만들기 때문에,
    생성자가 load()를 부르면 그게 곧 import 비용이 된다."""
    def explode():
        raise AssertionError("생성만으로 load()가 불렸다")

    monkeypatch.setattr(embeddings, "load", explode)
    embeddings.BGEM3OnnxEmbeddings()  # 예외가 안 나야 통과
    assert embeddings.get_status()["state"] == "idle"


def test_get_status_returns_a_copy():
    """호출부가 받은 dict를 만져도 내부 상태가 안 바뀌어야 한다 — 배경 스레드와 공유하는
    값이라 참조를 그대로 내주면 추적 불가능한 오염이 생긴다."""
    snapshot = embeddings.get_status()
    snapshot["state"] = "오염"
    assert embeddings.get_status()["state"] == "idle"


def _stub_heavy_deps(monkeypatch, calls: list):
    """snapshot_download·Tokenizer·InferenceSession을 전부 가짜로 바꾼다."""
    monkeypatch.setattr(embeddings, "snapshot_download", lambda *a, **kw: calls.append("download") or "/fake")

    class FakeTokenizer:
        @staticmethod
        def from_file(path):
            return FakeTokenizer()

        def enable_truncation(self, max_length):
            pass

    class FakeSession:
        def get_inputs(self):
            return [type("I", (), {"name": "input_ids"})()]

        def get_outputs(self):
            return [type("O", (), {"name": "sentence_embedding"})()]

    monkeypatch.setattr(embeddings, "Tokenizer", FakeTokenizer)
    monkeypatch.setattr(embeddings.ort, "InferenceSession", lambda *a, **kw: FakeSession())


def test_load_runs_once_and_reports_ready(monkeypatch):
    calls: list = []
    _stub_heavy_deps(monkeypatch, calls)

    first = embeddings.load()
    second = embeddings.load()

    assert first is second           # 같은 객체를 재사용
    assert calls == ["download"]     # 두 번째 호출은 다운로드를 다시 안 함
    assert embeddings.get_status()["state"] == "ready"


def test_concurrent_load_downloads_only_once(monkeypatch):
    """첫 질문과 배경 prefetch가 겹칠 수 있다 — 락이 없으면 2.1GB 준비가 두 번 돈다."""
    calls: list = []
    _stub_heavy_deps(monkeypatch, calls)

    threads = [threading.Thread(target=embeddings.load) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert calls == ["download"]


def test_load_failure_is_recorded_and_raised(monkeypatch):
    """실패를 상태에 남겨야 화면이 '준비 중'에 영영 머물지 않는다(§3 정직하게 실패)."""
    def boom(*a, **kw):
        raise OSError("네트워크 끊김")

    monkeypatch.setattr(embeddings, "snapshot_download", boom)

    with pytest.raises(OSError):
        embeddings.load()

    status = embeddings.get_status()
    assert status["state"] == "failed"
    assert "네트워크 끊김" in status["error"]


def test_prefetch_swallows_errors_but_records_them(monkeypatch):
    """배경 준비가 실패했다고 서버가 죽으면 안 된다."""
    def boom(*a, **kw):
        raise OSError("네트워크 끊김")

    monkeypatch.setattr(embeddings, "snapshot_download", boom)

    embeddings.prefetch()  # 예외가 밖으로 안 나와야 통과

    assert embeddings.get_status()["state"] == "failed"


def test_progress_tqdm_tracks_only_the_byte_bar():
    """huggingface_hub는 tqdm_class를 두 번 만든다 — 파일 개수 바와 바이트 집계 바.
    unit="B"인 쪽만 진행률로 잡아야 한다(개수 바까지 더하면 숫자가 엉킨다).

    아래 호출 순서는 _snapshot_download.py의 `_AggregatedTqdm`이 실제로 하는 것과 같다:
    총량을 더한 뒤 refresh(), 내려받은 만큼 update().
    """
    byte_bar = embeddings._ProgressTqdm(
        disable=True, name="test", desc="", total=0, initial=0, unit="B", unit_scale=True
    )
    byte_bar.total += 2_000
    byte_bar.refresh()
    byte_bar.update(800)

    file_bar = embeddings._ProgressTqdm(disable=True, name="test", desc="", total=10)
    file_bar.update(3)  # 파일 개수는 진행률에 섞이면 안 됨

    status = embeddings.get_status()
    assert status["total_bytes"] == 2_000
    assert status["downloaded_bytes"] == 800
