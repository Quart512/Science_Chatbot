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


def test_doi_and_arxiv_id_uniqueness_allows_multiple_nulls(conn):
    # doi가 둘 다 없는(NULL) 논문 두 개를 등록해도 UNIQUE 제약에 안 걸려야 한다
    # (SQLite는 NULL끼리는 서로 다른 값으로 취급 — 표준 SQL 동작)
    paper_catalog.upsert_recommended("hash:aaa", title="해시 기반 1", conn=conn)
    paper_catalog.upsert_recommended("hash:bbb", title="해시 기반 2", conn=conn)

    assert len(paper_catalog.list_papers(conn=conn)) == 2
