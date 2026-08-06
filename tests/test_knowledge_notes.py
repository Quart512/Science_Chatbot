"""
knowledge_notes.py — 지식 노트 CRUD. 진짜 텍스트는 SQLite(:memory:, interests.py/
equipment.py와 같은 패턴)에 두고, VDB는 검색용 청크만 담는 disposable 인덱스라
FakeVectorstore(tests/test_paper_ingest.py와 동일한 get/delete/add_texts 흉내)를
직접 주입해 검증한다. 실제 임베딩 모델·chroma_db는 건드리지 않음.
"""
import sqlite3

import pytest

import knowledge_notes


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    knowledge_notes.init_schema(c)
    yield c
    c.close()


class FakeVectorstore:
    """tests/test_paper_ingest.py의 FakeVectorstore와 동일 — get/delete/add_texts만
    흉내내는 인메모리 가짜(단일 키 dict where만 이해하면 충분)."""

    def __init__(self):
        self.ids: list[str] = []
        self.texts: list[str] = []
        self.metadatas: list[dict] = []
        self.delete_calls = 0

    def _matches(self, meta: dict, where: dict) -> bool:
        return all(meta.get(k) == v for k, v in where.items())

    def get(self, where: dict) -> dict:
        docs, metas = [], []
        for text, meta in zip(self.texts, self.metadatas):
            if self._matches(meta, where):
                docs.append(text)
                metas.append(meta)
        return {"documents": docs, "metadatas": metas}

    def delete(self, where: dict) -> None:
        self.delete_calls += 1
        keep = [not self._matches(m, where) for m in self.metadatas]
        self.ids = [i for i, k in zip(self.ids, keep) if k]
        self.texts = [t for t, k in zip(self.texts, keep) if k]
        self.metadatas = [m for m, k in zip(self.metadatas, keep) if k]

    def add_texts(self, texts, metadatas, ids) -> None:
        self.ids += list(ids)
        self.texts += list(texts)
        self.metadatas += list(metadatas)


@pytest.fixture
def vs():
    return FakeVectorstore()


# --- create_note() -------------------------------------------------------------


def test_create_note_returns_new_id(conn, vs):
    note_id = knowledge_notes.create_note("제목", "본문", conn=conn, vectorstore=vs)
    assert note_id == 1


def test_create_note_stores_title_and_text_in_sqlite(conn, vs):
    note_id = knowledge_notes.create_note("파인만 8장", "확률론적 해석의 핵심은...", conn=conn, vectorstore=vs)

    row = knowledge_notes.get_note(note_id, conn=conn)
    assert row["title"] == "파인만 8장"
    assert row["text"] == "확률론적 해석의 핵심은..."
    assert row["created_at"] == row["updated_at"]


def test_create_note_defaults_title_and_text_to_empty_string(conn, vs):
    note_id = knowledge_notes.create_note(conn=conn, vectorstore=vs)
    row = knowledge_notes.get_note(note_id, conn=conn)
    assert row["title"] == ""
    assert row["text"] == ""


def test_create_note_indexes_chunks_in_vectorstore(conn, vs):
    note_id = knowledge_notes.create_note("제목", "짧은 본문", conn=conn, vectorstore=vs)

    assert len(vs.texts) == 1  # 500자 미만이라 청크 하나
    assert vs.metadatas[0] == {"note_id": note_id, "source_type": "user_note"}


def test_create_note_with_empty_text_indexes_nothing(conn, vs):
    knowledge_notes.create_note("제목만", "", conn=conn, vectorstore=vs)
    assert vs.texts == []


# --- get_note() / list_notes() --------------------------------------------------


def test_get_note_returns_none_when_not_found(conn):
    assert knowledge_notes.get_note(999, conn=conn) is None


def test_get_note_does_not_touch_vectorstore(conn):
    # SQLite에서 그대로 읽으므로 vectorstore 인자 자체가 없다 — 청크 재조합이 필요 없다는
    # 이 설계의 핵심을 시그니처 자체로 확인.
    note_id = knowledge_notes.create_note("제목", "본문", conn=conn, vectorstore=FakeVectorstore())
    assert knowledge_notes.get_note(note_id, conn=conn)["text"] == "본문"


def test_list_notes_orders_by_sort_order(conn, vs):
    # 08-06 — 기본 정렬을 updated_at DESC(최근 수정 순)에서 수동 정렬(sort_order,
    # library_order.py)로 바꿨다. 새로 만든 노트는 끝에 붙는다(등록 순서 그대로).
    first_id = knowledge_notes.create_note("첫 번째", "a", conn=conn, vectorstore=vs)
    second_id = knowledge_notes.create_note("두 번째", "b", conn=conn, vectorstore=vs)

    notes = knowledge_notes.list_notes(conn=conn)
    assert [n["id"] for n in notes] == [first_id, second_id]

    # 수정해도(updated_at이 바뀌어도) 순서는 그대로 — 수동 정렬의 핵심 계약.
    knowledge_notes.update_note(first_id, conn=conn, vectorstore=vs, text="수정됨")
    notes = knowledge_notes.list_notes(conn=conn)
    assert [n["id"] for n in notes] == [first_id, second_id]


def test_move_note_swaps_with_neighbor(conn, vs):
    first_id = knowledge_notes.create_note("첫 번째", "a", conn=conn, vectorstore=vs)
    second_id = knowledge_notes.create_note("두 번째", "b", conn=conn, vectorstore=vs)

    assert knowledge_notes.move_note(second_id, "up", conn=conn) is True
    notes = knowledge_notes.list_notes(conn=conn)
    assert [n["id"] for n in notes] == [second_id, first_id]

    # 이미 맨 앞이라 더 못 올라감 — False, 순서도 그대로.
    assert knowledge_notes.move_note(second_id, "up", conn=conn) is False
    notes = knowledge_notes.list_notes(conn=conn)
    assert [n["id"] for n in notes] == [second_id, first_id]


def test_list_notes_title_search_is_substring(conn, vs):
    a = knowledge_notes.create_note("양자역학 메모", "본문", conn=conn, vectorstore=vs)
    knowledge_notes.create_note("고전역학 메모", "본문", conn=conn, vectorstore=vs)
    knowledge_notes.create_note("전혀 다른 제목", "본문", conn=conn, vectorstore=vs)

    matched = knowledge_notes.list_notes(q="양자", conn=conn)
    assert [n["id"] for n in matched] == [a]


# --- update_note() ---------------------------------------------------------------


def test_update_note_updates_title_only(conn, vs):
    note_id = knowledge_notes.create_note("원래 제목", "본문", conn=conn, vectorstore=vs)
    updated = knowledge_notes.update_note(note_id, title="고친 제목", conn=conn, vectorstore=vs)

    row = knowledge_notes.get_note(note_id, conn=conn)
    assert updated is True
    assert row["title"] == "고친 제목"
    assert row["text"] == "본문"  # text는 안 건드림


def test_update_note_title_only_does_not_reindex(conn, vs):
    note_id = knowledge_notes.create_note("제목", "본문", conn=conn, vectorstore=vs)
    before_ids = list(vs.ids)

    knowledge_notes.update_note(note_id, title="새 제목", conn=conn, vectorstore=vs)

    assert vs.ids == before_ids  # 청크가 그대로 유지됨(재색인 안 함)


def test_update_note_text_reindexes_vectorstore(conn, vs):
    note_id = knowledge_notes.create_note("제목", "원래 본문", conn=conn, vectorstore=vs)
    knowledge_notes.update_note(note_id, text="완전히 바뀐 새 본문", conn=conn, vectorstore=vs)

    assert vs.texts == ["완전히 바뀐 새 본문"]  # 옛 청크는 지워지고 새 청크로 교체(부분 재인코딩 아님)


def test_update_note_bumps_updated_at_but_not_created_at(conn, vs):
    note_id = knowledge_notes.create_note("제목", "본문", conn=conn, vectorstore=vs)
    before = knowledge_notes.get_note(note_id, conn=conn)

    knowledge_notes.update_note(note_id, title="고친 제목", conn=conn, vectorstore=vs)

    after = knowledge_notes.get_note(note_id, conn=conn)
    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] >= before["updated_at"]


def test_update_note_returns_false_when_id_not_found(conn, vs):
    assert knowledge_notes.update_note(999, title="유령", conn=conn, vectorstore=vs) is False


def test_update_note_rejects_unknown_field(conn, vs):
    note_id = knowledge_notes.create_note("제목", "본문", conn=conn, vectorstore=vs)
    with pytest.raises(ValueError):
        knowledge_notes.update_note(note_id, unknown_field="x", conn=conn, vectorstore=vs)


def test_update_note_with_no_fields_returns_false(conn, vs):
    note_id = knowledge_notes.create_note("제목", "본문", conn=conn, vectorstore=vs)
    assert knowledge_notes.update_note(note_id, conn=conn, vectorstore=vs) is False


# --- delete_note() ---------------------------------------------------------------


def test_delete_note_removes_row_and_chunks(conn, vs):
    note_id = knowledge_notes.create_note("제목", "본문", conn=conn, vectorstore=vs)
    deleted = knowledge_notes.delete_note(note_id, conn=conn, vectorstore=vs)

    assert deleted is True
    assert knowledge_notes.get_note(note_id, conn=conn) is None
    assert vs.texts == []


def test_delete_note_returns_false_when_id_not_found(conn, vs):
    assert knowledge_notes.delete_note(999, conn=conn, vectorstore=vs) is False


def test_delete_note_does_not_touch_vectorstore_when_not_found(conn, vs):
    # create_note() 자체가 내부적으로 _reindex()→vectorstore.delete()를 한 번 부르므로
    # (재등록 대비 선삭제 패턴), 그 이후 호출 횟수가 안 늘어나는지만 본다.
    knowledge_notes.create_note("살아있는 노트", "본문", conn=conn, vectorstore=vs)
    calls_before = vs.delete_calls

    knowledge_notes.delete_note(999, conn=conn, vectorstore=vs)

    assert vs.delete_calls == calls_before  # 존재하지 않는 id라 vectorstore.delete가 추가로 안 불림
