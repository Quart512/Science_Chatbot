"""
_add_tokens — graph.py의 순수 헬퍼. 여러 노드에 걸쳐 tokens_used를 누적할 때 쓴다.
합집합이 아니라 TOKEN_KEYS(input/output/total) 세 개만 골라서 더한다 — provider별로
딸려오는 input_token_details 같은 중첩 dict까지 합치려 하면 int+dict로 터지기 때문.
"""
from graph import _add_tokens


def test_add_tokens_sums_matching_keys():
    current = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    new = {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}
    assert _add_tokens(current, new) == {"input_tokens": 13, "output_tokens": 7, "total_tokens": 20}


def test_add_tokens_ignores_extra_keys_in_new():
    # provider별로 input_token_details 같은 중첩 dict가 섞여올 수 있음 — TOKEN_KEYS 외엔 무시해야 함
    current = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    new = {
        "input_tokens": 1,
        "output_tokens": 1,
        "total_tokens": 2,
        "input_token_details": {"cache_read": 1},
    }
    assert _add_tokens(current, new) == {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}


def test_add_tokens_defaults_missing_keys_to_zero():
    # new(외부 provider가 준 값)에 키가 아예 없는 경우(usage_metadata 누락 등)를 방어
    current = {"input_tokens": 4, "output_tokens": 4, "total_tokens": 8}
    assert _add_tokens(current, {}) == current
