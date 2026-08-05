"""
api_keys.py — 사용자 API 키 저장소(08-05 설정 화면). interests.py와 같은 패턴,
:memory: sqlite3 연결로 순수 로직만 검증.
"""
import sqlite3

import pytest

import api_keys


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    api_keys.init_schema(c)
    yield c
    c.close()


def test_get_api_key_returns_none_when_not_saved(conn):
    assert api_keys.get_api_key("gemini", conn=conn) is None


def test_set_then_get_api_key(conn):
    api_keys.set_api_key("gemini", "sk-test-1234", conn=conn)
    assert api_keys.get_api_key("gemini", conn=conn) == "sk-test-1234"


def test_set_api_key_upserts_existing_provider(conn):
    api_keys.set_api_key("gemini", "old-key", conn=conn)
    api_keys.set_api_key("gemini", "new-key", conn=conn)
    assert api_keys.get_api_key("gemini", conn=conn) == "new-key"


def test_set_api_key_rejects_empty_string(conn):
    with pytest.raises(ValueError):
        api_keys.set_api_key("gemini", "", conn=conn)


def test_set_api_key_rejects_unsupported_provider(conn):
    with pytest.raises(ValueError):
        api_keys.set_api_key("qwen-tuned", "irrelevant", conn=conn)


def test_get_api_key_rejects_unsupported_provider(conn):
    with pytest.raises(ValueError):
        api_keys.get_api_key("not-a-real-provider", conn=conn)


def test_delete_api_key_removes_saved_key(conn):
    api_keys.set_api_key("claude", "sk-claude-abcd", conn=conn)
    deleted = api_keys.delete_api_key("claude", conn=conn)
    assert deleted is True
    assert api_keys.get_api_key("claude", conn=conn) is None


def test_delete_api_key_returns_false_when_nothing_to_delete(conn):
    assert api_keys.delete_api_key("gemini", conn=conn) is False


def test_list_key_status_includes_all_supported_providers_even_unsaved(conn):
    api_keys.set_api_key("gemini", "sk-gemini-56789", conn=conn)
    statuses = api_keys.list_key_status(conn=conn)

    by_provider = {s["provider"]: s for s in statuses}
    assert set(by_provider) == set(api_keys.SUPPORTED_PROVIDERS)
    assert by_provider["gemini"]["saved"] is True
    assert by_provider["claude"]["saved"] is False
    assert by_provider["claude"]["masked_key"] is None


def test_list_key_status_masks_key_showing_only_last_four_chars(conn):
    api_keys.set_api_key("gemini", "sk-abcdefgh5678", conn=conn)
    statuses = api_keys.list_key_status(conn=conn)

    gemini_status = next(s for s in statuses if s["provider"] == "gemini")
    assert gemini_status["masked_key"].endswith("5678")
    assert "5678" not in gemini_status["masked_key"][:-4]
    assert gemini_status["masked_key"] != "sk-abcdefgh5678"  # 평문이 그대로 새면 안 됨


def test_list_key_status_masks_short_key_entirely(conn):
    # 4자 이하는 끝 4자리를 남기는 게 사실상 전체 노출과 같으므로 전부 마스킹
    api_keys.set_api_key("gemini", "abcd", conn=conn)
    statuses = api_keys.list_key_status(conn=conn)
    gemini_status = next(s for s in statuses if s["provider"] == "gemini")
    assert gemini_status["masked_key"] == "****"
