"""
register_paper / get_paper_summary — paper_ingest.py의 오케스트레이션 함수. 실제 PDF·임베딩
모델·LLM API를 전혀 건드리지 않는 톨게이트 테스트: parse_pdf/invoke_with_fallback은
monkeypatch로 갈아끼우고, vectorstore는 이 파일의 FakeVectorstore(인메모리 흉내)를
주입한다. pdf_path는 open(path, "rb")가 성공해야 하므로 pytest tmp_path로 실제 파일을
하나 만들지만(내용은 parse_pdf를 monkeypatch하므로 의미 없음), PyMuPDF는 전혀 호출되지 않는다.
"""
import pytest

import paper_ingest
from models import ContextBudgetExceeded
from paper_extraction import PaperExtraction


class FakeVectorstore:
    """chromadb 컬렉션의 get/delete/add_texts만 흉내내는 인메모리 가짜. 이 모듈이 실제로
    쓰는 where 형태(단일 키 dict / $and 다중조건)만 이해하면 되므로 그만큼만 구현한다."""

    def __init__(self):
        self.ids: list[str] = []
        self.texts: list[str] = []
        self.metadatas: list[dict] = []

    def _matches(self, meta: dict, where: dict) -> bool:
        if "$and" in where:
            return all(self._matches(meta, cond) for cond in where["$and"])
        return all(meta.get(k) == v for k, v in where.items())

    def get(self, where: dict) -> dict:
        docs, metas = [], []
        for text, meta in zip(self.texts, self.metadatas):
            if self._matches(meta, where):
                docs.append(text)
                metas.append(meta)
        return {"documents": docs, "metadatas": metas}

    def delete(self, where: dict) -> None:
        keep = [not self._matches(m, where) for m in self.metadatas]
        self.ids = [i for i, k in zip(self.ids, keep) if k]
        self.texts = [t for t, k in zip(self.texts, keep) if k]
        self.metadatas = [m for m, k in zip(self.metadatas, keep) if k]

    def add_texts(self, texts, metadatas, ids) -> None:
        self.ids += list(ids)
        self.texts += list(texts)
        self.metadatas += list(metadatas)


def _fake_parse_pdf(scanned=False, markdown="# Title\n\n## Body\n\n" + "내용입니다. " * 50):
    return {
        "text_extractable": not scanned,
        "markdown": markdown,
        "page_count": 3,
    }


@pytest.fixture(autouse=True)
def _reset_in_flight():
    # ensure_summary_in_background()의 모듈 전역 in-flight 집합은 프로세스 생명주기 동안
    # 유지되는 상태라, 테스트 간에 서로 오염되지 않도록 매 테스트 전후로 비운다.
    paper_ingest._IN_FLIGHT.clear()
    yield
    paper_ingest._IN_FLIGHT.clear()


# --- register_paper() ----------------------------------------------------


def test_register_paper_computes_paper_id_from_arxiv(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda path: _fake_parse_pdf())

    vs = FakeVectorstore()
    result = paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.12345", vectorstore=vs)

    assert result["paper_id"] == "arxiv:2401.12345"
    assert result["text_extractable"] is True
    assert result["chunk_count"] > 0
    assert len(vs.ids) == result["chunk_count"]


def test_register_paper_scanned_pdf_skips_chunking(monkeypatch, tmp_path):
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda path: _fake_parse_pdf(scanned=True))

    vs = FakeVectorstore()
    result = paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.99999", vectorstore=vs)

    assert result["text_extractable"] is False
    assert result["chunk_count"] == 0
    assert vs.ids == []  # 스캔본은 OCR도, 저장도 안 한다(pdf_parse.py 원칙 그대로 물려받음)


def test_register_paper_prioritizes_doi_over_arxiv(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda path: _fake_parse_pdf())

    vs = FakeVectorstore()
    result = paper_ingest.register_paper(
        str(pdf_path), doi="10.1234/abc", arxiv_id="2401.12345", vectorstore=vs
    )
    assert result["paper_id"] == "doi:10.1234/abc"


def test_register_paper_reregistration_replaces_old_chunks(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    vs = FakeVectorstore()

    monkeypatch.setattr(
        paper_ingest, "parse_pdf",
        lambda path: _fake_parse_pdf(markdown="# T\n\n## A\n\n" + "가나다라. " * 200),
    )
    first = paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.11111", vectorstore=vs)

    # 두 번째 등록은 내용이 훨씬 짧아 청크 수가 줄어드는 경우 — 재등록 시 이전 잔여 청크가
    # 안 남는지 확인 (RoadMap "재등록 처리" 참고)
    monkeypatch.setattr(
        paper_ingest, "parse_pdf",
        lambda path: _fake_parse_pdf(markdown="# T\n\n## A\n\n짧음"),
    )
    second = paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.11111", vectorstore=vs)

    assert first["chunk_count"] > second["chunk_count"]
    assert len(vs.ids) == second["chunk_count"]


def test_register_paper_stores_but_flags_references(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    md = "# T\n\n## Intro\n\n" + "본문 내용입니다. " * 30 + "\n\n## References\n\n" + "[1] 인용문헌. " * 30
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda path: _fake_parse_pdf(markdown=md))

    vs = FakeVectorstore()
    paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.22222", vectorstore=vs)

    assert any(m["is_references"] for m in vs.metadatas)  # 버리지 않고 저장은 됨
    assert any(not m["is_references"] for m in vs.metadatas)  # 일반 섹션도 그대로 있음


def test_register_paper_flattens_bibliographic_list_fields(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda path: _fake_parse_pdf())

    vs = FakeVectorstore()
    paper_ingest.register_paper(
        str(pdf_path),
        arxiv_id="2401.33333",
        bibliographic={"title": "테스트 논문", "authors": ["김", "이"], "year": None},
        vectorstore=vs,
    )

    meta = vs.metadatas[0]
    assert meta["title"] == "테스트 논문"
    assert meta["authors"] == "김, 이"  # 리스트 -> 문자열
    assert "year" not in meta  # None은 키 자체를 생략


# --- get_paper_summary() --------------------------------------------------


def test_get_paper_summary_returns_cached_without_llm_call(monkeypatch):
    vs = FakeVectorstore()
    cached = PaperExtraction(core_claims=["기존 캐시된 주장"])
    vs.add_texts(
        texts=["요약 텍스트"],
        metadatas=[{"paper_id": "arxiv:1", "doc_type": "summary", "extraction_json": cached.model_dump_json()}],
        ids=["arxiv:1-summary"],
    )

    def _boom(*a, **kw):
        raise AssertionError("캐시가 있으면 invoke_with_fallback을 부르면 안 됨")
    monkeypatch.setattr(paper_ingest, "invoke_with_fallback", _boom)

    result = paper_ingest.get_paper_summary("arxiv:1", vectorstore=vs)
    assert result["from_cache"] is True
    assert result["extraction"].core_claims == ["기존 캐시된 주장"]


def test_get_paper_summary_raises_if_not_registered():
    vs = FakeVectorstore()
    with pytest.raises(ValueError):
        paper_ingest.get_paper_summary("arxiv:없음", vectorstore=vs)


def test_get_paper_summary_excludes_references_chunks_from_llm_input(monkeypatch):
    vs = FakeVectorstore()
    vs.add_texts(
        texts=["본문 청크", "References 청크"],
        metadatas=[
            {"paper_id": "arxiv:1", "doc_type": "fulltext_chunk", "index": 0, "is_references": False, "header": "Intro"},
            {"paper_id": "arxiv:1", "doc_type": "fulltext_chunk", "index": 1, "is_references": True, "header": "References"},
        ],
        ids=["arxiv:1-0", "arxiv:1-1"],
    )

    captured = {}
    def _fake_invoke(model, messages, structured=None):
        captured["full_text"] = messages[-1].content
        return (
            PaperExtraction(core_claims=["추출됨"]),
            "gemini",
            [],
            {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        )
    monkeypatch.setattr(paper_ingest, "invoke_with_fallback", _fake_invoke)

    result = paper_ingest.get_paper_summary("arxiv:1", vectorstore=vs)

    assert "본문 청크" in captured["full_text"]
    assert "References 청크" not in captured["full_text"]
    assert result["from_cache"] is False
    assert result["extraction"].core_claims == ["추출됨"]
    assert any(m["doc_type"] == "summary" for m in vs.metadatas)  # 결과가 캐시로 저장됨


def test_get_paper_summary_propagates_context_budget_exceeded(monkeypatch):
    vs = FakeVectorstore()
    vs.add_texts(
        texts=["x" * 999_999],
        metadatas=[{"paper_id": "arxiv:1", "doc_type": "fulltext_chunk", "index": 0, "is_references": False, "header": "A"}],
        ids=["arxiv:1-0"],
    )

    def _boom(*a, **kw):
        raise AssertionError("예산 초과면 invoke_with_fallback을 부르면 안 됨")
    monkeypatch.setattr(paper_ingest, "invoke_with_fallback", _boom)

    with pytest.raises(ContextBudgetExceeded):
        paper_ingest.get_paper_summary("arxiv:1", model="Qwen-tuned", vectorstore=vs)


# --- ensure_summary_in_background() ---------------------------------------


def test_ensure_summary_in_background_skips_when_already_cached(monkeypatch):
    vs = FakeVectorstore()
    cached = PaperExtraction(core_claims=["기존 캐시된 주장"])
    vs.add_texts(
        texts=["요약 텍스트"],
        metadatas=[{"paper_id": "arxiv:cached", "doc_type": "summary", "extraction_json": cached.model_dump_json()}],
        ids=["arxiv:cached-summary"],
    )

    def _boom(fn):
        raise AssertionError("이미 요약이 있으면 백그라운드를 띄우면 안 됨")
    monkeypatch.setattr(paper_ingest, "_spawn_background", _boom)

    result = paper_ingest.ensure_summary_in_background("arxiv:cached", vectorstore=vs)
    assert result is False


def test_ensure_summary_in_background_generates_and_clears_in_flight(monkeypatch):
    vs = FakeVectorstore()
    vs.add_texts(
        texts=["본문 청크"],
        metadatas=[{"paper_id": "arxiv:new", "doc_type": "fulltext_chunk", "index": 0, "is_references": False, "header": "A"}],
        ids=["arxiv:new-0"],
    )
    # _spawn_background를 동기 실행으로 갈아끼워 진짜 스레드 없이 fn()을 바로 돌린다
    monkeypatch.setattr(paper_ingest, "_spawn_background", lambda fn: fn())
    monkeypatch.setattr(paper_ingest, "invoke_with_fallback", lambda *a, **kw: (
        PaperExtraction(core_claims=["백그라운드에서 추출됨"]),
        "gemini",
        [],
        {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    ))

    result = paper_ingest.ensure_summary_in_background("arxiv:new", vectorstore=vs)

    assert result is True
    assert paper_ingest._IN_FLIGHT == set()  # 완료 후 in-flight 표시가 지워짐
    assert any(m["doc_type"] == "summary" for m in vs.metadatas)  # 실제로 캐시에 저장됨


def test_ensure_summary_in_background_dedupes_concurrent_calls(monkeypatch):
    vs = FakeVectorstore()
    vs.add_texts(
        texts=["본문 청크"],
        metadatas=[{"paper_id": "arxiv:dup", "doc_type": "fulltext_chunk", "index": 0, "is_references": False, "header": "A"}],
        ids=["arxiv:dup-0"],
    )
    started_fns = []
    # 일부러 fn()을 실행하지 않는다 — "아직 완료되지 않은 백그라운드 작업" 상태를 그대로
    # 유지해야 두 번째 호출이 in-flight 가드에 걸리는지 확인할 수 있다.
    monkeypatch.setattr(paper_ingest, "_spawn_background", lambda fn: started_fns.append(fn))

    first = paper_ingest.ensure_summary_in_background("arxiv:dup", vectorstore=vs)
    second = paper_ingest.ensure_summary_in_background("arxiv:dup", vectorstore=vs)

    assert first is True
    assert second is False  # 이미 진행 중이므로 중복으로 안 띄움
    assert len(started_fns) == 1


def test_ensure_summary_in_background_clears_in_flight_even_on_failure(monkeypatch):
    vs = FakeVectorstore()
    vs.add_texts(
        texts=["본문 청크"],
        metadatas=[{"paper_id": "arxiv:fail", "doc_type": "fulltext_chunk", "index": 0, "is_references": False, "header": "A"}],
        ids=["arxiv:fail-0"],
    )
    monkeypatch.setattr(paper_ingest, "_spawn_background", lambda fn: fn())

    def _fail(*a, **kw):
        raise RuntimeError("LLM 호출 실패")
    monkeypatch.setattr(paper_ingest, "invoke_with_fallback", _fail)

    result = paper_ingest.ensure_summary_in_background("arxiv:fail", vectorstore=vs)

    assert result is True  # 시작 자체는 됐음(백그라운드 안에서 실패한 것)
    assert paper_ingest._IN_FLIGHT == set()  # 실패해도 지워져야 다음 호출에서 재시도 가능
