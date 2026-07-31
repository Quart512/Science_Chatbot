"""
POST /interests — 08-07 호출 경로(07-31). "관심사 등록" 버튼이 부르는 단순 엔드포인트.
interests.py의 CRUD를 몽키패치해 라우팅·분기 로직만 검증 — 실제 DB 파일은 안 건드림.
TestClient(main.app)는 lifespan(AsyncSqliteSaver)도 함께 돈다 — /query와 무관한 엔드포인트
테스트라도 앱을 띄우는 이상 거쳐가는 경로이므로 그대로 둔다(가볍고 실제 파일 I/O만 발생).
"""
from fastapi.testclient import TestClient

import interests
import main
import paper_recommend


def test_register_interest_creates_new_when_no_update_id(monkeypatch):
    captured = {}
    def _fake_create(title, looking_for="", already_known="", excluded_topics="", **kw):
        captured.update(title=title, looking_for=looking_for)
        return 42
    monkeypatch.setattr(interests, "create_interest", _fake_create)

    with TestClient(main.app) as client:
        resp = client.post("/interests", json={"title": "제목", "looking_for": "찾는것"})

    assert resp.status_code == 200
    assert resp.json() == {"interest_id": 42, "action": "created"}
    assert captured == {"title": "제목", "looking_for": "찾는것"}


def test_register_interest_updates_existing_when_update_id_given(monkeypatch):
    captured = {}
    def _fake_update(interest_id, **fields):
        captured["id"] = interest_id
        captured["fields"] = fields
        return True
    monkeypatch.setattr(interests, "update_interest", _fake_update)

    with TestClient(main.app) as client:
        resp = client.post(
            "/interests",
            json={"title": "고친 제목", "looking_for": "", "update_existing_id": 7},
        )

    assert resp.status_code == 200
    assert resp.json() == {"interest_id": 7, "action": "updated"}
    assert captured["id"] == 7
    assert captured["fields"]["title"] == "고친 제목"


def test_register_interest_404_when_update_id_not_found(monkeypatch):
    monkeypatch.setattr(interests, "update_interest", lambda interest_id, **fields: False)

    with TestClient(main.app) as client:
        resp = client.post("/interests", json={"title": "제목", "update_existing_id": 999})

    assert resp.status_code == 404


# --- POST /interests/{id}/search (08-09③ 호출 경로) -------------------------


def test_trigger_recommend_search_returns_results(monkeypatch):
    fake_results = [{"paper_id": "arxiv:1", "title": "논문", "is_relevant": True}]
    monkeypatch.setattr(paper_recommend, "recommend_for_interest", lambda interest_id, **kw: fake_results)

    with TestClient(main.app) as client:
        resp = client.post("/interests/1/search")

    assert resp.status_code == 200
    assert resp.json() == {"recommended": fake_results}


def test_trigger_recommend_search_404_when_interest_not_found(monkeypatch):
    def _boom(interest_id, **kw):
        raise ValueError(f"관심사 id={interest_id}를 찾을 수 없습니다")
    monkeypatch.setattr(paper_recommend, "recommend_for_interest", _boom)

    with TestClient(main.app) as client:
        resp = client.post("/interests/999/search")

    assert resp.status_code == 404
