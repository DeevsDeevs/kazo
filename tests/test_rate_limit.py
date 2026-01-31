import time

import pytest

from kazo.claude.client import RateLimitExceeded, _enforce_rate_limit
from kazo.main import _rate_limit_windows, check_rate_limit, record_rate_limit


@pytest.fixture(autouse=True)
def clear_windows():
    _rate_limit_windows.clear()
    yield
    _rate_limit_windows.clear()


def test_allows_under_limit():
    assert check_rate_limit(1) is True


def test_blocks_at_limit():
    now = time.monotonic()
    _rate_limit_windows[1] = [now - i for i in range(30)]
    assert check_rate_limit(1) is False


def test_expired_entries_pruned():
    _rate_limit_windows[1] = [time.monotonic() - 3700 for _ in range(50)]
    assert check_rate_limit(1) is True


def test_record_increments():
    record_rate_limit(1)
    assert len(_rate_limit_windows[1]) == 1


def test_per_chat_isolation():
    now = time.monotonic()
    _rate_limit_windows[1] = [now - i for i in range(30)]
    assert check_rate_limit(1) is False
    assert check_rate_limit(2) is True


def test_enforce_rate_limit_raises():
    now = time.monotonic()
    _rate_limit_windows[1] = [now - i for i in range(30)]
    with pytest.raises(RateLimitExceeded):
        _enforce_rate_limit(1)


def test_enforce_rate_limit_records():
    _enforce_rate_limit(1)
    assert len(_rate_limit_windows[1]) == 1
