"""
paper_catalog.py — 논문 카탈로그 RDB(SQLite) CRUD. interests.py와 같은 이유로 가짜
객체 없이 sqlite3 ":memory:" 연결을 그대로 쓴다.
"""
import sqlite3

import pytest

import paper_catalog


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    paper_catalog.init_schema(c)
    yield c
    c.close()


def test_init_schema_adds_missing_filename_column_to_existing_table():
    # filename이 없던 시절에 만들어진 DB — 실제 배포 환경(EC2 바인드 마운트)에 남아있을
    # 수 있는 상태다. equipment.py가 precautions 컬럼에서 실제로 겪은 문제와 같은
    # 패턴(CREATE TABLE IF NOT EXISTS만으로는 컬럼이 안 생김).
    old = sqlite3.connect(":memory:")
    old.row_factory = sqlite3.Row
    old.executescript("""
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT UNIQUE,
            arxiv_id TEXT UNIQUE,
            title TEXT NOT NULL DEFAULT '',
            authors TEXT NOT NULL DEFAULT '',
            year TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'recommended',
            journal_ref TEXT,
            citation_count INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    old.execute(
        "INSERT INTO papers (paper_id, title, created_at, updated_at) VALUES ('hash:old', '구형 논문', 'x', 'x')"
    )
    old.commit()

    paper_catalog.init_schema(old)

    paper_catalog.mark_owned("hash:new", filename="새논문.pdf", conn=old)
    assert paper_catalog.get_paper("hash:new", conn=old)["filename"] == "새논문.pdf"
    assert paper_catalog.get_paper("hash:old", conn=old)["filename"] == ""  # 기존 행은 DEFAULT로 채워짐
    old.close()


def test_upsert_recommended_inserts_new_paper(conn):
    added = paper_catalog.upsert_recommended(
        "arxiv:2401.1", arxiv_id="2401.1", title="테스트 논문", authors="김, 이", year="2024", conn=conn
    )
    row = paper_catalog.get_paper("arxiv:2401.1", conn=conn)

    assert added is True
    assert row["status"] == "recommended"
    assert row["title"] == "테스트 논문"
    assert row["created_at"] == row["updated_at"]


def test_upsert_recommended_skips_when_already_exists(conn):
    paper_catalog.upsert_recommended("arxiv:2401.1", title="원래 제목", conn=conn)
    added_again = paper_catalog.upsert_recommended("arxiv:2401.1", title="다른 제목으로 덮어쓰기 시도", conn=conn)

    row = paper_catalog.get_paper("arxiv:2401.1", conn=conn)
    assert added_again is False
    assert row["title"] == "원래 제목"  # 이미 있으면 손대지 않음


def test_upsert_recommended_does_not_downgrade_owned_paper(conn):
    # 이미 owned인 논문을 추천 검색이 다시 찾아내도 recommended로 되돌리면 안 된다
    paper_catalog.mark_owned("arxiv:2401.1", title="보유 중인 논문", conn=conn)
    added = paper_catalog.upsert_recommended("arxiv:2401.1", title="추천으로 다시 발견됨", conn=conn)

    row = paper_catalog.get_paper("arxiv:2401.1", conn=conn)
    assert added is False
    assert row["status"] == "owned"  # 여전히 owned


def test_mark_owned_creates_row_when_not_recommended_first(conn):
    # 추천된 적 없이 바로 등록된 논문 — 새로 만들어져야 함
    paper_catalog.mark_owned("doi:10.1234/x", doi="10.1234/x", title="바로 등록", conn=conn)
    row = paper_catalog.get_paper("doi:10.1234/x", conn=conn)

    assert row["status"] == "owned"
    assert row["title"] == "바로 등록"


def test_mark_owned_transitions_existing_recommended_to_owned(conn):
    paper_catalog.upsert_recommended("arxiv:2401.1", title="추천됨", conn=conn)
    paper_catalog.mark_owned("arxiv:2401.1", conn=conn)

    row = paper_catalog.get_paper("arxiv:2401.1", conn=conn)
    assert row["status"] == "owned"
    assert row["title"] == "추천됨"  # mark_owned가 title을 안 넘겼으면 기존 값 유지


def test_mark_owned_stores_filename_on_new_row(conn):
    # title이 비어있는 논문(서지정보를 못 찾은 경우) 화면 표시용 차선책 — 08-04 사용자 요청.
    paper_catalog.mark_owned("hash:abcd", filename="내논문.pdf", conn=conn)
    row = paper_catalog.get_paper("hash:abcd", conn=conn)

    assert row["filename"] == "내논문.pdf"


def test_mark_owned_backfills_filename_on_promoted_row(conn):
    # 추천으로 먼저 생긴 행(filename 없음)을 나중에 실제로 업로드해 owned로 승격할 때도
    # filename이 채워져야 한다 — 추천 경로엔 애초에 업로드 파일이 없어 채울 기회가 없었음.
    paper_catalog.upsert_recommended("arxiv:2401.1", title="추천됨", conn=conn)
    paper_catalog.mark_owned("arxiv:2401.1", filename="업로드한파일.pdf", conn=conn)

    row = paper_catalog.get_paper("arxiv:2401.1", conn=conn)
    assert row["filename"] == "업로드한파일.pdf"


def test_mark_owned_stores_file_path_and_content_sha256_on_new_row(conn):
    # ②-B(08-05) — library/ 경유 등록 시 file_path·content_sha256이 filename과 같은
    # 방식으로 저장돼야 한다.
    paper_catalog.mark_owned(
        "hash:abcd", file_path="quantum/paper.pdf", content_sha256="deadbeef", conn=conn
    )
    row = paper_catalog.get_paper("hash:abcd", conn=conn)

    assert row["file_path"] == "quantum/paper.pdf"
    assert row["content_sha256"] == "deadbeef"


def test_mark_owned_backfills_file_path_on_promoted_row(conn):
    # filename과 같은 이유(추천 경로엔 파일이 없어 채울 기회가 없었음) — library/에서
    # "트래킹에 추가"로 승격할 때도 file_path가 누락되지 않아야 한다.
    paper_catalog.upsert_recommended("arxiv:2401.1", title="추천됨", conn=conn)
    paper_catalog.mark_owned(
        "arxiv:2401.1", file_path="quantum/paper.pdf", content_sha256="deadbeef", conn=conn
    )

    row = paper_catalog.get_paper("arxiv:2401.1", conn=conn)
    assert row["file_path"] == "quantum/paper.pdf"
    assert row["content_sha256"] == "deadbeef"


def test_dismiss_marks_status_and_returns_true(conn):
    paper_catalog.upsert_recommended("arxiv:2401.1", title="기각될 논문", conn=conn)
    result = paper_catalog.dismiss("arxiv:2401.1", conn=conn)

    assert result is True
    assert paper_catalog.get_paper("arxiv:2401.1", conn=conn)["status"] == "dismissed"


def test_dismiss_returns_false_when_paper_not_found(conn):
    assert paper_catalog.dismiss("arxiv:없음", conn=conn) is False


def test_get_paper_returns_none_when_not_found(conn):
    assert paper_catalog.get_paper("arxiv:없음", conn=conn) is None


def test_list_papers_filters_by_status(conn):
    paper_catalog.upsert_recommended("arxiv:1", title="추천1", conn=conn)
    paper_catalog.upsert_recommended("arxiv:2", title="추천2", conn=conn)
    paper_catalog.mark_owned("arxiv:2", conn=conn)

    recommended = paper_catalog.list_papers(status="recommended", conn=conn)
    owned = paper_catalog.list_papers(status="owned", conn=conn)
    all_papers = paper_catalog.list_papers(conn=conn)

    assert [p["paper_id"] for p in recommended] == ["arxiv:1"]
    assert [p["paper_id"] for p in owned] == ["arxiv:2"]
    assert len(all_papers) == 2


# --- interest_paper (08-03) ----------------------------------------------------


def test_record_screening_inserts_new_row(conn):
    paper_catalog.record_screening(1, "arxiv:1", is_relevant=True, reasoning="관련 있음", conn=conn)
    paper_catalog.upsert_recommended("arxiv:1", title="논문1", conn=conn)

    rows = paper_catalog.list_papers_for_interest(1, conn=conn)

    assert len(rows) == 1
    assert rows[0]["paper_id"] == "arxiv:1"
    assert rows[0]["is_relevant"] is True
    assert rows[0]["reasoning"] == "관련 있음"
    assert rows[0]["title"] == "논문1"  # papers와 조인돼 서지정보도 같이 나옴


def test_record_screening_includes_irrelevant_candidates(conn):
    # 카탈로그(upsert_recommended)와 달리 관련 없다고 판정된 것도 기록해야 한다 —
    # "이 관심사에 무엇이 스크리닝됐나"의 전체 기록이 목적이라서다. 실제 호출부
    # (paper_recommend.py)는 관련 없으면 upsert_recommended를 안 부르므로 papers에
    # 행이 없는 채로 조회돼야 한다(LEFT JOIN 확인 겸함).
    paper_catalog.record_screening(1, "arxiv:1", is_relevant=False, reasoning="무관함", conn=conn)

    rows = paper_catalog.list_papers_for_interest(1, conn=conn)
    assert len(rows) == 1
    assert rows[0]["paper_id"] == "arxiv:1"
    assert rows[0]["is_relevant"] is False
    assert rows[0]["title"] is None  # papers 테이블에 행 자체가 없음


def test_record_screening_overwrites_on_rescreen(conn):
    # 재스크리닝(refresh_for_interest)이 같은 쌍을 다시 채점하면 최신 판정으로
    # 덮어써야 한다 — upsert_recommended와 달리 이 값은 사용자 결정이 아니다.
    paper_catalog.record_screening(1, "arxiv:1", is_relevant=False, reasoning="처음엔 무관", conn=conn)
    paper_catalog.record_screening(1, "arxiv:1", is_relevant=True, reasoning="다시 보니 관련 있음", conn=conn)

    rows = paper_catalog.list_papers_for_interest(1, conn=conn)
    assert len(rows) == 1  # 새 행이 생기지 않고 덮어씀
    assert rows[0]["is_relevant"] is True
    assert rows[0]["reasoning"] == "다시 보니 관련 있음"


def test_list_papers_for_interest_scoped_to_that_interest(conn):
    # 다대다 확인 — 같은 논문이 여러 관심사에 걸릴 수 있고, 조회는 그 관심사 것만 봐야 함
    paper_catalog.upsert_recommended("arxiv:1", title="논문1", conn=conn)
    paper_catalog.record_screening(1, "arxiv:1", is_relevant=True, reasoning="관심사1 근거", conn=conn)
    paper_catalog.record_screening(2, "arxiv:1", is_relevant=True, reasoning="관심사2 근거", conn=conn)

    interest1_papers = paper_catalog.list_papers_for_interest(1, conn=conn)
    interest2_papers = paper_catalog.list_papers_for_interest(2, conn=conn)

    assert len(interest1_papers) == 1
    assert interest1_papers[0]["reasoning"] == "관심사1 근거"
    assert len(interest2_papers) == 1
    assert interest2_papers[0]["reasoning"] == "관심사2 근거"


def test_list_papers_for_interest_only_relevant_filters(conn):
    paper_catalog.upsert_recommended("arxiv:1", title="관련", conn=conn)
    paper_catalog.upsert_recommended("arxiv:2", title="무관", conn=conn)
    paper_catalog.record_screening(1, "arxiv:1", is_relevant=True, reasoning="", conn=conn)
    paper_catalog.record_screening(1, "arxiv:2", is_relevant=False, reasoning="", conn=conn)

    all_papers = paper_catalog.list_papers_for_interest(1, conn=conn)
    relevant_only = paper_catalog.list_papers_for_interest(1, only_relevant=True, conn=conn)

    assert len(all_papers) == 2
    assert [p["paper_id"] for p in relevant_only] == ["arxiv:1"]


def test_list_papers_for_interest_returns_empty_when_none_screened(conn):
    assert paper_catalog.list_papers_for_interest(999, conn=conn) == []


def test_delete_screenings_for_interest_removes_only_that_interests_rows(conn):
    # 08-04 버그 수정 — 관심사 삭제 시 이 함수가 안 불리면 interest_paper가 고아로 남는다.
    paper_catalog.upsert_recommended("arxiv:1", title="논문1", conn=conn)
    paper_catalog.record_screening(1, "arxiv:1", is_relevant=True, reasoning="관심사1 근거", conn=conn)
    paper_catalog.record_screening(2, "arxiv:1", is_relevant=True, reasoning="관심사2 근거", conn=conn)

    paper_catalog.delete_screenings_for_interest(1, conn=conn)

    assert paper_catalog.list_papers_for_interest(1, conn=conn) == []
    assert len(paper_catalog.list_papers_for_interest(2, conn=conn)) == 1  # 다른 관심사 것은 안 건드림


def test_delete_screenings_for_interest_no_error_when_none_exist(conn):
    paper_catalog.delete_screenings_for_interest(999, conn=conn)  # 예외 없이 끝나야 함


def test_doi_and_arxiv_id_uniqueness_allows_multiple_nulls(conn):
    # doi가 둘 다 없는(NULL) 논문 두 개를 등록해도 UNIQUE 제약에 안 걸려야 한다
    # (SQLite는 NULL끼리는 서로 다른 값으로 취급 — 표준 SQL 동작)
    paper_catalog.upsert_recommended("hash:aaa", title="해시 기반 1", conn=conn)
    paper_catalog.upsert_recommended("hash:bbb", title="해시 기반 2", conn=conn)

    assert len(paper_catalog.list_papers(conn=conn)) == 2


def test_scan_library_files_marks_tracked_by_file_path(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(paper_catalog, "LIBRARY_DIR", str(tmp_path))
    (tmp_path / "quantum").mkdir()
    (tmp_path / "quantum" / "tracked.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "untracked.pdf").write_bytes(b"%PDF-1.4 fake")
    conn.execute(
        "INSERT INTO papers (paper_id, file_path, created_at, updated_at) VALUES (?, ?, 'x', 'x')",
        ("hash:aaa", "quantum/tracked.pdf"),
    )

    files = paper_catalog.scan_library_files(conn=conn)

    assert files == [
        {"path": "quantum/tracked.pdf", "tracked": True},
        {"path": "untracked.pdf", "tracked": False},
    ]


def test_scan_library_files_ignores_non_pdf(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(paper_catalog, "LIBRARY_DIR", str(tmp_path))
    (tmp_path / "notes.txt").write_bytes(b"not a pdf")

    assert paper_catalog.scan_library_files(conn=conn) == []


def test_scan_library_files_empty_when_library_dir_missing(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(paper_catalog, "LIBRARY_DIR", str(tmp_path / "does-not-exist"))

    assert paper_catalog.scan_library_files(conn=conn) == []


def test_resolve_library_path_returns_absolute_path_inside_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paper_catalog, "LIBRARY_DIR", str(tmp_path))
    (tmp_path / "quantum").mkdir()
    (tmp_path / "quantum" / "paper.pdf").write_bytes(b"%PDF-1.4 fake")

    resolved = paper_catalog.resolve_library_path("quantum/paper.pdf")

    assert resolved == str((tmp_path / "quantum" / "paper.pdf").resolve())


def test_resolve_library_path_rejects_traversal_outside_root(tmp_path, monkeypatch):
    library_dir = tmp_path / "library"
    library_dir.mkdir()
    monkeypatch.setattr(paper_catalog, "LIBRARY_DIR", str(library_dir))

    with pytest.raises(ValueError):
        paper_catalog.resolve_library_path("../outside.pdf")
