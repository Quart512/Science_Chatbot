"""
register_paper / get_paper_summary — paper_ingest.py의 오케스트레이션 함수. 실제 PDF·임베딩
모델·LLM API를 전혀 건드리지 않는 톨게이트 테스트: parse_pdf/invoke_with_fallback은
monkeypatch로 갈아끼우고, vectorstore는 이 파일의 FakeVectorstore(인메모리 흉내)를
주입한다. pdf_path는 open(path, "rb")가 성공해야 하므로 pytest tmp_path로 실제 파일을
하나 만들지만(내용은 parse_pdf를 monkeypatch하므로 의미 없음), PyMuPDF는 전혀 호출되지 않는다.
"""
import pytest

from models import ContextBudgetExceeded
from paper import paper_ingest
from paper.paper_extraction import PaperExtraction


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


def _fake_parse_pdf(scanned=False, markdown="# Title\n\n## Body\n\n" + "내용입니다. " * 50, pdf_title=None):
    return {
        "text_extractable": not scanned,
        "markdown": markdown,
        "page_count": 3,
        "pdf_title": pdf_title,
    }


@pytest.fixture(autouse=True)
def _reset_in_flight():
    # ensure_summary_in_background()의 모듈 전역 상태(in-flight 집합, 영구 실패 집합)는
    # 프로세스 생명주기 동안 유지되는 상태라, 테스트 간에 서로 오염되지 않도록 매 테스트
    # 전후로 비운다.
    paper_ingest._IN_FLIGHT.clear()
    paper_ingest._PERMANENTLY_FAILED.clear()
    yield
    paper_ingest._IN_FLIGHT.clear()
    paper_ingest._PERMANENTLY_FAILED.clear()


@pytest.fixture(autouse=True)
def _stub_paper_catalog(monkeypatch):
    # register_paper()는 08-09 마무리로 정상 등록 시 paper_catalog.mark_owned()를 부른다.
    # 기본값은 실제 data/app.db(interests.APP_DB_PATH)를 여는 함수라, 여기서 기본으로
    # no-op 스텁해두지 않으면 이 파일의 모든 테스트가 진짜 sqlite 파일을 건드리게 된다
    # (위 _stub_arxiv_fetch와 같은 이유). 카탈로그 연동 자체를 검증하는 테스트는 이
    # 스텁을 자기 목적에 맞는 기록용 가짜로 다시 덮어쓴다.
    monkeypatch.setattr(paper_ingest.paper_catalog, "mark_owned", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _stub_arxiv_fetch(monkeypatch):
    # register_paper()는 arxiv_id가 있고 bibliographic에 abstract가 없으면 자동으로
    # arxiv API(fetch_by_id)를 호출한다(07-29) — 이 파일 대부분의 테스트는 그 자동 조회
    # 로직 자체를 보는 게 아니므로 기본은 "못 찾음"(None)으로 스텁해 실제 네트워크 호출을
    # 막는다(톨게이트 테스트는 네트워크 없이 1~2초에 끝나야 한다는 원칙, 처음엔 이 스텁 없이
    # 커밋했다가 기존 테스트들이 진짜 네트워크를 타는 걸로 뒤늦게 발견함). 자동 조회 자체를
    # 검증하는 테스트들(아래 "arxiv API 자동 서지정보 조회" 섹션)은 각자 이 스텁을 자기
    # 목적에 맞는 가짜로 다시 덮어쓴다.
    monkeypatch.setattr(paper_ingest, "fetch_by_id", lambda arxiv_id: None)


# --- register_paper() ----------------------------------------------------


def test_register_paper_computes_paper_id_from_arxiv(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

    vs = FakeVectorstore()
    result = paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.12345", vectorstore=vs)

    assert result["paper_id"] == "arxiv:2401.12345"
    assert result["text_extractable"] is True
    assert result["chunk_count"] > 0
    assert len(vs.ids) == result["chunk_count"]


def test_register_paper_scanned_pdf_skips_chunking(monkeypatch, tmp_path):
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf(scanned=True))

    vs = FakeVectorstore()
    result = paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.99999", vectorstore=vs)

    assert result["text_extractable"] is False
    assert result["chunk_count"] == 0
    assert vs.ids == []  # 스캔본은 OCR도, 저장도 안 한다(pdf_parse.py 원칙 그대로 물려받음)


def test_register_paper_marks_catalog_owned(monkeypatch, tmp_path):
    # 08-09 마무리 — 정상 등록되면 paper_catalog.mark_owned()가 paper_id·doi·arxiv_id·
    # bib_meta(title/authors/year)를 그대로 넘겨받는지 확인. bib_meta의 authors는
    # _flatten_bibliographic()이 list를 콤마로 합친 문자열이어야 한다(기존 "리스트
    # 필드를 평탄화" 테스트와 같은 형태를 mark_owned 호출 인자에서도 재확인).
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

    calls = []
    monkeypatch.setattr(
        paper_ingest.paper_catalog,
        "mark_owned",
        lambda paper_id, **kwargs: calls.append((paper_id, kwargs)),
    )

    vs = FakeVectorstore()
    bibliographic = {"title": "테스트 논문", "authors": ["김철수", "이영희"], "year": 2024}
    result = paper_ingest.register_paper(
        str(pdf_path), arxiv_id="2401.12345", bibliographic=bibliographic,
        filename="원본파일.pdf", vectorstore=vs,
    )

    assert len(calls) == 1
    paper_id, kwargs = calls[0]
    assert paper_id == result["paper_id"]
    assert kwargs["doi"] is None
    assert kwargs["arxiv_id"] == "2401.12345"
    assert kwargs["title"] == "테스트 논문"
    assert kwargs["authors"] == "김철수, 이영희"
    assert kwargs["year"] == 2024
    assert kwargs["filename"] == "원본파일.pdf"


def test_register_paper_defaults_filename_to_empty_string(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

    calls = []
    monkeypatch.setattr(
        paper_ingest.paper_catalog, "mark_owned", lambda paper_id, **kwargs: calls.append(kwargs)
    )

    paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.12346", vectorstore=FakeVectorstore())

    assert calls[0]["filename"] == ""


def test_register_paper_passes_file_path_to_catalog(monkeypatch, tmp_path):
    # ②-B(08-05) — library/ 경유 등록("트래킹에 추가")이면 file_path가 그대로 mark_owned에
    # 전달돼야 한다. 기존 업로드 다이얼로그 경로는 file_path를 안 넘기므로 기본값 None이
    # 그대로 전달되는지는 아래 별도 테스트에서 확인.
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

    calls = []
    monkeypatch.setattr(
        paper_ingest.paper_catalog, "mark_owned", lambda paper_id, **kwargs: calls.append(kwargs)
    )

    paper_ingest.register_paper(
        str(pdf_path), arxiv_id="2401.12347", file_path="quantum/paper.pdf", vectorstore=FakeVectorstore()
    )

    assert calls[0]["file_path"] == "quantum/paper.pdf"


def test_register_paper_computes_content_sha256_even_without_file_path(monkeypatch, tmp_path):
    # content_sha256(설계 노트 항목 C)은 file_path 유무와 무관하게 항상 계산된다 —
    # DOI/arXiv 논문은 paper_id가 해시가 아니라 이 컬럼이 유일한 내용 매칭 수단이므로.
    import hashlib

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

    calls = []
    monkeypatch.setattr(
        paper_ingest.paper_catalog, "mark_owned", lambda paper_id, **kwargs: calls.append(kwargs)
    )

    paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.12348", vectorstore=FakeVectorstore())

    assert calls[0]["file_path"] is None
    assert calls[0]["content_sha256"] == hashlib.sha256(b"dummy").hexdigest()


def test_register_paper_scanned_pdf_skips_catalog(monkeypatch, tmp_path):
    # 스캔본은 VDB에 아무것도 저장하지 않는 것과 대칭으로 카탈로그도 안 건드린다 —
    # "파싱해서 실제로 확보된 논문"만 owned로 표시한다는 설계 그대로.
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf(scanned=True))

    calls = []
    monkeypatch.setattr(
        paper_ingest.paper_catalog, "mark_owned", lambda *a, **k: calls.append((a, k))
    )

    vs = FakeVectorstore()
    paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.99999", vectorstore=vs)

    assert calls == []


def test_register_paper_prioritizes_doi_over_arxiv(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

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
        lambda file_bytes: _fake_parse_pdf(markdown="# T\n\n## A\n\n" + "가나다라. " * 200),
    )
    first = paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.11111", vectorstore=vs)

    # 두 번째 등록은 내용이 훨씬 짧아 청크 수가 줄어드는 경우 — 재등록 시 이전 잔여 청크가
    # 안 남는지 확인 (RoadMap "재등록 처리" 참고)
    monkeypatch.setattr(
        paper_ingest, "parse_pdf",
        lambda file_bytes: _fake_parse_pdf(markdown="# T\n\n## A\n\n짧음"),
    )
    second = paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.11111", vectorstore=vs)

    assert first["chunk_count"] > second["chunk_count"]
    assert len(vs.ids) == second["chunk_count"]


def test_register_paper_clears_permanently_failed_on_reregistration(monkeypatch, tmp_path):
    # 재등록 = 요약 캐시 무효화와 같은 논리(모듈 docstring "재등록 처리" 참고) — 전문이
    # 바뀌면 전에 예산을 넘었던 논문이 이번엔 안 넘을 수 있으므로, "영구 실패" 기록도
    # 같이 지워져야 재시도가 막히지 않는다(07-28 리뷰 지적).
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

    vs = FakeVectorstore()
    paper_id = "arxiv:2401.55555"
    paper_ingest._PERMANENTLY_FAILED.add(paper_id)

    paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.55555", vectorstore=vs)

    assert paper_id not in paper_ingest._PERMANENTLY_FAILED


def test_register_paper_stores_but_flags_references(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    md = "# T\n\n## Intro\n\n" + "본문 내용입니다. " * 30 + "\n\n## References\n\n" + "[1] 인용문헌. " * 30
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf(markdown=md))

    vs = FakeVectorstore()
    paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.22222", vectorstore=vs)

    assert any(m["is_references"] for m in vs.metadatas)  # 버리지 않고 저장은 됨
    assert any(not m["is_references"] for m in vs.metadatas)  # 일반 섹션도 그대로 있음


def test_register_paper_flattens_bibliographic_list_fields(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

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


def test_register_paper_drops_non_whitelisted_bibliographic_fields(monkeypatch, tmp_path):
    # abstract처럼 화이트리스트에 없는 긴 필드를 그대로 받으면 청크 수만큼 그대로
    # 복제돼 VDB에 쌓인다(07-28 리뷰에서 발견된 버그) — 화이트리스트가 청크 메타데이터
    # 복제는 막는지 확인한다(abstract 자체의 별도 저장은 아래 abstract 테스트들 참고).
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    md = "# T\n\n## A\n\n" + "본문 내용입니다. " * 100  # 청크가 여러 개 나오도록 충분히 길게
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf(markdown=md))

    vs = FakeVectorstore()
    long_abstract = "이 논문의 초록입니다. " * 100
    result = paper_ingest.register_paper(
        str(pdf_path),
        arxiv_id="2401.44444",
        bibliographic={"title": "테스트 논문", "abstract": long_abstract, "unknown_field": "아무거나"},
        vectorstore=vs,
    )

    chunk_metas = [m for m in vs.metadatas if m["doc_type"] == "fulltext_chunk"]
    assert result["chunk_count"] > 1  # 청크가 여러 개 나와야 "복제되면 몇 부씩 쌓이는지"가 의미 있음
    assert all("abstract" not in m for m in chunk_metas)
    assert all("unknown_field" not in m for m in chunk_metas)
    assert all(m["title"] == "테스트 논문" for m in chunk_metas)  # 화이트리스트에 있는 건 그대로 유지


# --- arxiv API 자동 서지정보 조회 (07-29) ----------------------------------
# fetch_by_id()(arxiv_api.py, 네트워크 호출)를 monkeypatch로 갈아끼워 register_paper()의
# 분기(언제 부르고 언제 건너뛰는지, 실패 시 등록을 막지 않는지)만 검증한다.


def test_register_paper_auto_fetches_bibliographic_when_missing(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())
    monkeypatch.setattr(
        paper_ingest, "fetch_by_id",
        lambda arxiv_id: {"title": "arxiv에서 가져온 제목", "abstract": "arxiv에서 가져온 초록"},
    )

    vs = FakeVectorstore()
    paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.66666", vectorstore=vs)

    chunk_metas = [m for m in vs.metadatas if m["doc_type"] == "fulltext_chunk"]
    assert all(m["title"] == "arxiv에서 가져온 제목" for m in chunk_metas)
    abstract_docs = [t for t, m in zip(vs.texts, vs.metadatas) if m["doc_type"] == "abstract"]
    assert abstract_docs == ["arxiv에서 가져온 초록"]


def test_register_paper_skips_auto_fetch_when_abstract_already_given(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

    def _boom(arxiv_id):
        raise AssertionError("bibliographic에 abstract가 이미 있으면 자동 조회를 하면 안 됨")
    monkeypatch.setattr(paper_ingest, "fetch_by_id", _boom)

    vs = FakeVectorstore()
    paper_ingest.register_paper(
        str(pdf_path), arxiv_id="2401.66667",
        bibliographic={"abstract": "이미 있는 초록"}, vectorstore=vs,
    )  # _boom이 호출되면 AssertionError로 여기서 실패


def test_register_paper_skips_auto_fetch_without_arxiv_id(monkeypatch, tmp_path):
    # DOI만 있거나 아무 식별자도 없으면(해시 기반 paper_id) 조회할 arxiv_id 자체가 없다
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

    def _boom(arxiv_id):
        raise AssertionError("arxiv_id가 없으면 자동 조회를 하면 안 됨")
    monkeypatch.setattr(paper_ingest, "fetch_by_id", _boom)

    vs = FakeVectorstore()
    paper_ingest.register_paper(str(pdf_path), doi="10.1234/xyz", vectorstore=vs)


def test_register_paper_explicit_bibliographic_overrides_fetched(monkeypatch, tmp_path):
    # 호출자가 명시적으로 넘긴 값이 자동 조회 결과보다 우선해야 한다 — 조회는 빈 자리만 채움
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())
    monkeypatch.setattr(
        paper_ingest, "fetch_by_id",
        lambda arxiv_id: {"title": "arxiv 제목", "abstract": "arxiv 초록"},
    )

    vs = FakeVectorstore()
    paper_ingest.register_paper(
        str(pdf_path), arxiv_id="2401.66668",
        bibliographic={"title": "사용자가 지정한 제목"}, vectorstore=vs,
    )

    chunk_metas = [m for m in vs.metadatas if m["doc_type"] == "fulltext_chunk"]
    assert all(m["title"] == "사용자가 지정한 제목" for m in chunk_metas)  # 명시값 유지
    abstract_docs = [t for t, m in zip(vs.texts, vs.metadatas) if m["doc_type"] == "abstract"]
    assert abstract_docs == ["arxiv 초록"]  # 없던 자리는 조회 결과로 채워짐


def test_register_paper_none_bibliographic_value_does_not_override_fetched(monkeypatch, tmp_path):
    # 호출자가 {"title": None}처럼 "모른다"는 뜻으로 None을 넘겨도, 그 None이 arxiv
    # 조회 결과를 덮어쓰면 안 된다 — 키가 있다는 이유만으로 우선시키면(**딕셔너리 병합은
    # 값이 None이든 아니든 키 존재만 본다) 방금 가져온 title이 사라지는 버그가 있었다.
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())
    monkeypatch.setattr(
        paper_ingest, "fetch_by_id",
        lambda arxiv_id: {"title": "arxiv 제목", "abstract": "arxiv 초록"},
    )

    vs = FakeVectorstore()
    paper_ingest.register_paper(
        str(pdf_path), arxiv_id="2401.66669",
        bibliographic={"title": None}, vectorstore=vs,
    )

    chunk_metas = [m for m in vs.metadatas if m["doc_type"] == "fulltext_chunk"]
    assert all(m["title"] == "arxiv 제목" for m in chunk_metas)  # None에 안 덮임


def test_register_paper_continues_when_arxiv_fetch_fails(monkeypatch, tmp_path):
    # 네트워크 오류 등으로 조회가 실패해도 등록 자체는 막으면 안 된다 — 서지정보 없이 진행
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

    def _fail(arxiv_id):
        raise ConnectionError("네트워크 실패 흉내")
    monkeypatch.setattr(paper_ingest, "fetch_by_id", _fail)

    vs = FakeVectorstore()
    result = paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.66669", vectorstore=vs)

    assert result["text_extractable"] is True
    assert result["chunk_count"] > 0
    assert not any(m["doc_type"] == "abstract" for m in vs.metadatas)  # 서지정보 없음 → abstract도 없음


# --- abstract 확보 (07-29, 6-3 후속) --------------------------------------


def test_register_paper_stores_arxiv_abstract_once(monkeypatch, tmp_path):
    # 위 test_register_paper_drops_non_whitelisted_bibliographic_fields가 "청크에
    # 복제되지 않는다"를 확인했다면, 이 테스트는 그 abstract가 아예 버려지는 게 아니라
    # doc_type="abstract" 문서 하나로(딱 한 번) 저장되는지 확인한다.
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

    vs = FakeVectorstore()
    abstract_text = "이 논문의 초록입니다."
    paper_ingest.register_paper(
        str(pdf_path),
        arxiv_id="2401.44444",
        bibliographic={"abstract": abstract_text},
        vectorstore=vs,
    )

    abstract_docs = [t for t, m in zip(vs.texts, vs.metadatas) if m["doc_type"] == "abstract"]
    assert abstract_docs == [abstract_text]


def test_register_paper_abstract_doc_carries_title(monkeypatch, tmp_path):
    # abstract 문서도 bib_meta(title 등)를 같이 받아야 한다(07-29, 답변 근거 표시 작업 중
    # 발견) — 안 그러면 fulltext_chunk 없이 abstract만 검색됐을 때 어느 논문인지
    # paper_id로만 표시된다. register_paper()가 이미 들고 있는 bib_meta를 재사용하는
    # 것뿐이라 청크마다 복제되는 문제(_BIBLIOGRAPHIC_WHITELIST)와는 무관 — 문서 1개.
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())

    vs = FakeVectorstore()
    paper_ingest.register_paper(
        str(pdf_path),
        arxiv_id="2401.44445",
        bibliographic={"title": "테스트 논문", "abstract": "초록 내용"},
        vectorstore=vs,
    )

    abstract_meta = next(m for m in vs.metadatas if m["doc_type"] == "abstract")
    assert abstract_meta["title"] == "테스트 논문"


def test_register_paper_falls_back_to_pdf_abstract_section(monkeypatch, tmp_path):
    # arxiv 서지정보에 abstract가 없으면(예: 업로드 PDF만 있고 arxiv_id가 없는 경우)
    # PDF 자체의 Abstract 섹션에서 뽑아야 한다 — extract_abstract()(paper_chunking.py)가
    # 이미 계산해둔 pieces에서 골라내므로 재파싱은 필요 없다.
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    md = "# T\n\n## Abstract\n\n논문 초록 본문입니다.\n\n## Introduction\n\n" + "본문. " * 30
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf(markdown=md))

    vs = FakeVectorstore()
    paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.55556", vectorstore=vs)

    abstract_docs = [t for t, m in zip(vs.texts, vs.metadatas) if m["doc_type"] == "abstract"]
    assert len(abstract_docs) == 1
    assert "논문 초록 본문입니다." in abstract_docs[0]


def test_register_paper_prioritizes_arxiv_abstract_over_pdf_section(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    md = "# T\n\n## Abstract\n\nPDF에서 뽑힌 초록.\n\n## Introduction\n\n" + "본문. " * 30
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf(markdown=md))

    vs = FakeVectorstore()
    paper_ingest.register_paper(
        str(pdf_path),
        arxiv_id="2401.55557",
        bibliographic={"abstract": "arxiv가 준 초록."},
        vectorstore=vs,
    )

    abstract_docs = [t for t, m in zip(vs.texts, vs.metadatas) if m["doc_type"] == "abstract"]
    assert abstract_docs == ["arxiv가 준 초록."]


def test_register_paper_skips_abstract_doc_when_none_found(monkeypatch, tmp_path):
    # arxiv abstract도 없고 PDF에 Abstract 헤더도 없으면(헤더 인식 실패 등) abstract
    # 문서를 아예 안 만들어야 한다 — 없는 것을 빈 문자열로라도 저장하면 "값이 없음"과
    # "빈 문자열이 실제 값"을 구분 못 하게 된다(_flatten_bibliographic과 같은 원칙).
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())  # 헤더: Body

    vs = FakeVectorstore()
    paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.55558", vectorstore=vs)

    assert not any(m["doc_type"] == "abstract" for m in vs.metadatas)


# --- title_check (07-29, 6-3b③) --------------------------------------------


def test_register_paper_reports_match_when_titles_agree(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(
        paper_ingest, "parse_pdf",
        lambda file_bytes: _fake_parse_pdf(pdf_title="Quantum Entanglement Review"),
    )

    vs = FakeVectorstore()
    result = paper_ingest.register_paper(
        str(pdf_path), arxiv_id="2401.77771",
        bibliographic={"title": "Quantum Entanglement Review"}, vectorstore=vs,
    )

    assert result["title_check"]["status"] == "match"
    assert result["title_check"]["given_title"] == "Quantum Entanglement Review"
    assert result["title_check"]["pdf_title"] == "Quantum Entanglement Review"


def test_register_paper_reports_different_paper_when_titles_disagree(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(
        paper_ingest, "parse_pdf",
        lambda file_bytes: _fake_parse_pdf(pdf_title="A Survey of Kubernetes Deployment Strategies"),
    )

    vs = FakeVectorstore()
    result = paper_ingest.register_paper(
        str(pdf_path), arxiv_id="2401.77772",
        bibliographic={"title": "Quantum Entanglement Review"}, vectorstore=vs,
    )

    # 딴 논문일 가능성이 있다는 판정만 반환할 뿐, 등록 자체는 그대로 진행된다(막지 않음)
    assert result["title_check"]["status"] == "different_paper"
    assert result["text_extractable"] is True
    assert result["chunk_count"] > 0


def test_register_paper_reports_no_comparison_when_pdf_title_missing(monkeypatch, tmp_path):
    # PDF 제목 추출 실패는 불일치가 아니다(title_check.py 모듈 docstring 참고) — 조용히 건너뜀
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf(pdf_title=None))

    vs = FakeVectorstore()
    result = paper_ingest.register_paper(
        str(pdf_path), arxiv_id="2401.77773",
        bibliographic={"title": "Quantum Entanglement Review"}, vectorstore=vs,
    )

    assert result["title_check"]["status"] == "no_comparison"


def test_register_paper_reports_no_comparison_when_no_given_title(monkeypatch, tmp_path):
    # bibliographic 자체가 없는 경우(해시 기반 paper_id) — 대조할 기준이 없음
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(
        paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf(pdf_title="Some PDF Title")
    )

    vs = FakeVectorstore()
    result = paper_ingest.register_paper(str(pdf_path), vectorstore=vs)

    assert result["title_check"]["status"] == "no_comparison"


def test_register_paper_scanned_pdf_has_no_title_check(monkeypatch, tmp_path):
    # 스캔본은 저장할 게 없으니 검증도 의미가 없다(모듈 docstring 참고) — title_check 자체가 반환값에 없음
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"dummy")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf(scanned=True))

    vs = FakeVectorstore()
    result = paper_ingest.register_paper(str(pdf_path), arxiv_id="2401.77774", vectorstore=vs)

    assert "title_check" not in result


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


def test_get_paper_summary_carries_title_from_chunks_into_summary_doc(monkeypatch):
    # summary 문서엔 title이 없어서 답변 근거 표시에서 paper_id로만 보이던 문제(07-29,
    # graph.describe_context_sources 작업 중 발견) — register_paper()가 이미 청크에
    # 복제해둔 title을 _fetch_fulltext()가 청크와 함께 가져와 summary 문서에도 넣어야 한다.
    vs = FakeVectorstore()
    vs.add_texts(
        texts=["본문 청크"],
        metadatas=[{
            "paper_id": "arxiv:1", "doc_type": "fulltext_chunk", "index": 0,
            "is_references": False, "header": "Intro", "title": "테스트 논문",
        }],
        ids=["arxiv:1-0"],
    )
    monkeypatch.setattr(
        paper_ingest, "invoke_with_fallback",
        lambda model, messages, structured=None: (
            PaperExtraction(core_claims=["추출됨"]), "gemini", [],
            {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        ),
    )

    paper_ingest.get_paper_summary("arxiv:1", vectorstore=vs)

    summary_meta = next(m for m in vs.metadatas if m["doc_type"] == "summary")
    assert summary_meta["title"] == "테스트 논문"


# --- abstract를 추출 프롬프트 앵커로 제공 (07-29, 6-3b②) --------------------


def _add_fulltext_chunk(vs, paper_id="arxiv:1", text="본문 청크"):
    vs.add_texts(
        texts=[text],
        metadatas=[{"paper_id": paper_id, "doc_type": "fulltext_chunk", "index": 0, "is_references": False, "header": "Intro"}],
        ids=[f"{paper_id}-0"],
    )


def _add_abstract_doc(vs, paper_id="arxiv:1", text="이 논문의 초록"):
    vs.add_texts(texts=[text], metadatas=[{"paper_id": paper_id, "doc_type": "abstract"}], ids=[f"{paper_id}-abstract"])


def test_get_paper_summary_anchors_abstract_when_present(monkeypatch):
    vs = FakeVectorstore()
    _add_fulltext_chunk(vs)
    _add_abstract_doc(vs, text="이 논문의 초록입니다")

    captured = {}
    def _fake_invoke(model, messages, structured=None):
        captured["system"] = messages[0].content
        captured["human"] = messages[1].content
        return (PaperExtraction(core_claims=["추출됨"]), "gemini", [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})
    monkeypatch.setattr(paper_ingest, "invoke_with_fallback", _fake_invoke)

    paper_ingest.get_paper_summary("arxiv:1", vectorstore=vs)

    assert "[논문 초록]" in captured["human"]
    assert "이 논문의 초록입니다" in captured["human"]
    assert captured["human"].index("이 논문의 초록입니다") < captured["human"].index("본문 청크")  # 초록이 본문보다 앞
    assert paper_ingest.ABSTRACT_ANCHOR_INSTRUCTION in captured["system"]


def test_get_paper_summary_unchanged_when_no_abstract(monkeypatch):
    # abstract 문서가 없으면(bibliographic·PDF Abstract 섹션 둘 다 없던 논문) 프롬프트가
    # 전혀 안 바뀌어야 한다 — 회귀 없음 확인
    vs = FakeVectorstore()
    _add_fulltext_chunk(vs)

    captured = {}
    def _fake_invoke(model, messages, structured=None):
        captured["system"] = messages[0].content
        captured["human"] = messages[1].content
        return (PaperExtraction(core_claims=["추출됨"]), "gemini", [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})
    monkeypatch.setattr(paper_ingest, "invoke_with_fallback", _fake_invoke)

    paper_ingest.get_paper_summary("arxiv:1", vectorstore=vs)

    assert captured["human"] == "본문 청크"
    assert captured["system"] == paper_ingest.EXTRACTION_SYSTEM_PROMPT


def test_get_paper_summary_checks_budget_on_combined_text_with_abstract(monkeypatch):
    # full_text 단독으로는 예산 안이지만 abstract를 더하면 넘는 경계 케이스 —
    # full_text만 검사하면 여기서 안 걸리고 실제 API 호출에서야 예상 못 한 실패가 난다
    vs = FakeVectorstore()
    _add_fulltext_chunk(vs, text="x" * 5_950)  # Qwen-tuned 예산 6,000자 — 이 자체는 안 넘음
    _add_abstract_doc(vs, text="y" * 200)  # 앵커 텍스트("[논문 초록]\n...\n\n[본문]\n") 포함하면 넘김

    def _boom(*a, **kw):
        raise AssertionError("예산 초과면 invoke_with_fallback을 부르면 안 됨")
    monkeypatch.setattr(paper_ingest, "invoke_with_fallback", _boom)

    with pytest.raises(ContextBudgetExceeded):
        paper_ingest.get_paper_summary("arxiv:1", model="Qwen-tuned", vectorstore=vs)


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


def test_get_paper_summary_treats_missing_extraction_json_as_cache_miss(monkeypatch):
    # doc_type="summary" 문서는 있는데 extraction_json 키가 없는 경우(스키마 변경·다른
    # 경로로 생긴 문서 등) — metadatas[0]["extraction_json"]로 바로 읽으면 KeyError로
    # 조회 자체가 터진다. .get()으로 받아 캐시 미스로 취급하고 정상적으로 재생성으로
    # 넘어가는지 확인한다(07-28 리뷰 지적).
    vs = FakeVectorstore()
    vs.add_texts(
        texts=["깨진 요약 문서"],
        metadatas=[{"paper_id": "arxiv:1", "doc_type": "summary"}],  # extraction_json 없음
        ids=["arxiv:1-summary"],
    )
    vs.add_texts(
        texts=["본문 청크"],
        metadatas=[{"paper_id": "arxiv:1", "doc_type": "fulltext_chunk", "index": 0, "is_references": False, "header": "A"}],
        ids=["arxiv:1-0"],
    )
    monkeypatch.setattr(paper_ingest, "invoke_with_fallback", lambda *a, **kw: (
        PaperExtraction(core_claims=["재생성됨"]), "gemini", [], {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    ))

    result = paper_ingest.get_paper_summary("arxiv:1", vectorstore=vs)

    assert result["from_cache"] is False
    assert result["extraction"].core_claims == ["재생성됨"]


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


def test_ensure_summary_in_background_context_budget_exceeded_is_not_retried(monkeypatch):
    # ContextBudgetExceeded는 같은 모델·같은 전문 텍스트로는 재시도해도 항상 똑같이
    # 실패하는 결정론적 실패다 — 한 번 실패하면 _PERMANENTLY_FAILED에 기록되고, 이후
    # 호출은 스레드를 새로 안 띄워야 한다(07-28 리뷰 지적: negative caching 없이는
    # 매 retrieve()마다 똑같이 실패할 스레드를 계속 띄우게 됨).
    vs = FakeVectorstore()
    vs.add_texts(
        # Qwen-tuned 예산(6,000자)을 확실히 넘도록 충분히 길게 — 실제 check_context_budget()이
        # ContextBudgetExceeded를 던지게 하는 게 이 테스트의 핵심이라 짧으면 의미가 없다.
        texts=["x" * 10_000],
        metadatas=[{"paper_id": "arxiv:budget", "doc_type": "fulltext_chunk", "index": 0, "is_references": False, "header": "A"}],
        ids=["arxiv:budget-0"],
    )
    spawn_calls = []
    def _run_synchronously(fn):
        spawn_calls.append(fn)
        fn()
    monkeypatch.setattr(paper_ingest, "_spawn_background", _run_synchronously)

    # model="Qwen-tuned"(예산 6,000자)로 강제해 실제 LLM 없이도 check_context_budget()이
    # 예산 초과를 확실히 감지하게 한다 — invoke_with_fallback까지 가면 안 되므로 호출되면
    # 바로 실패하는 가짜로 갈아끼워 "여기까지 오면 테스트 설계가 잘못된 것"을 드러낸다.
    def _boom(*a, **kw):
        raise AssertionError("예산 초과면 invoke_with_fallback을 부르면 안 됨")
    monkeypatch.setattr(paper_ingest, "invoke_with_fallback", _boom)

    first = paper_ingest.ensure_summary_in_background("arxiv:budget", model="Qwen-tuned", vectorstore=vs)
    assert first is True  # 시작 자체는 됨(백그라운드 안에서 예산 초과로 실패)
    assert "arxiv:budget" in paper_ingest._PERMANENTLY_FAILED
    assert paper_ingest._IN_FLIGHT == set()

    second = paper_ingest.ensure_summary_in_background("arxiv:budget", model="Qwen-tuned", vectorstore=vs)
    assert second is False  # 영구 실패로 기록됐으므로 다시 스레드를 안 띄움
    assert len(spawn_calls) == 1  # 두 번째 호출에서 _spawn_background가 다시 불리지 않음


# --- track_in_background() (④ 파싱 분리, 08-05) ----------------------------


def test_track_in_background_creates_pending_row_and_returns_immediately(monkeypatch, tmp_path):
    import hashlib

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy content")
    expected_hash = hashlib.sha256(b"dummy content").hexdigest()

    monkeypatch.setattr(paper_ingest.paper_catalog, "get_paper", lambda paper_id: None)
    calls = []
    monkeypatch.setattr(
        paper_ingest.paper_catalog, "mark_owned",
        lambda paper_id, **kwargs: calls.append((paper_id, kwargs)),
    )
    # 스레드를 아예 안 돌린다 — 이 테스트는 "빠른 등록" 단계만 본다.
    monkeypatch.setattr(paper_ingest, "_spawn_background", lambda fn: None)

    result = paper_ingest.track_in_background(str(pdf_path), file_path="quantum/paper.pdf", filename="paper.pdf")

    assert result == {"paper_id": f"hash:{expected_hash}", "analysis_status": "pending"}
    assert len(calls) == 1
    paper_id, kwargs = calls[0]
    assert paper_id == f"hash:{expected_hash}"
    assert kwargs["file_path"] == "quantum/paper.pdf"
    assert kwargs["content_sha256"] == expected_hash
    assert kwargs["analysis_status"] == "pending"
    assert kwargs["filename"] == "paper.pdf"


def test_track_in_background_skips_spawn_when_already_in_progress(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy content")

    monkeypatch.setattr(
        paper_ingest.paper_catalog, "get_paper",
        lambda paper_id: {"paper_id": paper_id, "analysis_status": "analyzing"},
    )

    def _boom_mark_owned(*a, **kw):
        raise AssertionError("이미 진행 중이면 mark_owned를 다시 부르면 안 됨")
    monkeypatch.setattr(paper_ingest.paper_catalog, "mark_owned", _boom_mark_owned)

    def _boom_spawn(fn):
        raise AssertionError("이미 진행 중이면 스레드를 새로 띄우면 안 됨")
    monkeypatch.setattr(paper_ingest, "_spawn_background", _boom_spawn)

    result = paper_ingest.track_in_background(str(pdf_path), file_path="quantum/paper.pdf", filename="paper.pdf")

    assert result["analysis_status"] == "analyzing"  # 기존 상태를 그대로 돌려줌(재시도 아님)


def test_track_in_background_completes_full_pipeline_synchronously(monkeypatch, tmp_path):
    # _spawn_background를 동기 실행으로 갈아끼워 register_paper() 전체(파싱만 몽키패치,
    # 나머지는 진짜)가 끝까지 돌고 analysis_status가 pending → analyzing → (register_paper의
    # mark_owned 기본값)done 순서로 찍히는지 확인한다.
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"dummy content")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf())
    monkeypatch.setattr(paper_ingest.paper_catalog, "get_paper", lambda paper_id: None)
    monkeypatch.setattr(paper_ingest, "_spawn_background", lambda fn: fn())

    calls = []
    monkeypatch.setattr(
        paper_ingest.paper_catalog, "mark_owned",
        lambda paper_id, **kwargs: calls.append(("mark_owned", paper_id, kwargs)),
    )
    monkeypatch.setattr(
        paper_ingest.paper_catalog, "set_analysis_status",
        lambda paper_id, status, **kw: calls.append(("set_analysis_status", paper_id, status)),
    )

    result = paper_ingest.track_in_background(
        str(pdf_path), file_path="quantum/paper.pdf", filename="paper.pdf", vectorstore=FakeVectorstore()
    )

    assert result["analysis_status"] == "pending"
    kinds = [c[0] for c in calls]
    assert kinds == ["mark_owned", "set_analysis_status", "mark_owned"]
    assert calls[0][2]["analysis_status"] == "pending"
    assert calls[1][2] == "analyzing"
    assert "analysis_status" not in calls[2][2]  # register_paper()는 mark_owned 기본값(done)에 맡김


def test_track_in_background_marks_failed_on_scanned_pdf(monkeypatch, tmp_path):
    # ②-B에서 "④가 다룰 문제"로 미뤄뒀던 간극 — 스캔본은 register_paper()가 mark_owned()를
    # 안 타서 done이 자동으로 안 찍히므로, track_in_background()가 명시적으로 failed 처리한다.
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"dummy content")
    monkeypatch.setattr(paper_ingest, "parse_pdf", lambda file_bytes: _fake_parse_pdf(scanned=True))
    monkeypatch.setattr(paper_ingest.paper_catalog, "get_paper", lambda paper_id: None)
    monkeypatch.setattr(paper_ingest, "_spawn_background", lambda fn: fn())
    monkeypatch.setattr(paper_ingest.paper_catalog, "mark_owned", lambda paper_id, **kwargs: None)

    statuses = []
    monkeypatch.setattr(
        paper_ingest.paper_catalog, "set_analysis_status",
        lambda paper_id, status, **kw: statuses.append(status),
    )

    paper_ingest.track_in_background(str(pdf_path), file_path="quantum/scanned.pdf", filename="scanned.pdf")

    assert statuses == ["analyzing", "failed"]


def test_track_in_background_marks_failed_on_exception(monkeypatch, tmp_path):
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"dummy content")

    def _boom_parse(file_bytes):
        raise RuntimeError("파싱 실패")
    monkeypatch.setattr(paper_ingest, "parse_pdf", _boom_parse)
    monkeypatch.setattr(paper_ingest.paper_catalog, "get_paper", lambda paper_id: None)
    monkeypatch.setattr(paper_ingest, "_spawn_background", lambda fn: fn())
    monkeypatch.setattr(paper_ingest.paper_catalog, "mark_owned", lambda paper_id, **kwargs: None)

    statuses = []
    monkeypatch.setattr(
        paper_ingest.paper_catalog, "set_analysis_status",
        lambda paper_id, status, **kw: statuses.append(status),
    )

    paper_ingest.track_in_background(str(pdf_path), file_path="quantum/broken.pdf", filename="broken.pdf")

    assert statuses == ["analyzing", "failed"]
