import pytest
from fastapi import HTTPException

from app.core.rate_limit import check_rate_limit, reset_rate_limits


def setup_function():
    reset_rate_limits()


def test_allows_within_limit():
    for _ in range(5):
        check_rate_limit("k1", limit=5, window_seconds=60)


def test_blocks_beyond_limit():
    for _ in range(3):
        check_rate_limit("k2", limit=3, window_seconds=60)
    with pytest.raises(HTTPException) as exc:
        check_rate_limit("k2", limit=3, window_seconds=60)
    assert exc.value.status_code == 429


def test_keys_are_isolated():
    for _ in range(3):
        check_rate_limit("userA", limit=3, window_seconds=60)
    # 另一个 key 不受影响
    check_rate_limit("userB", limit=3, window_seconds=60)


def test_limit_zero_disables():
    for _ in range(100):
        check_rate_limit("k3", limit=0, window_seconds=60)


def test_window_expires(monkeypatch):
    import app.core.rate_limit as rl

    for _ in range(2):
        check_rate_limit("k4", limit=2, window_seconds=60)

    base = rl.time.monotonic()
    monkeypatch.setattr(rl.time, "monotonic", lambda: base + 61)
    check_rate_limit("k4", limit=2, window_seconds=60)

