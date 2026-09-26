import time

import pytest

from ttl_cache import ttl_cache


def test_cache_reuses_value_until_expiry():
    calls = {"count": 0}

    @ttl_cache(ttl_seconds=0.2)
    def expensive(value):
        calls["count"] += 1
        return value * 2

    assert expensive(3) == 6
    assert expensive(3) == 6
    assert calls["count"] == 1

    time.sleep(0.25)

    assert expensive(3) == 6
    assert calls["count"] == 2


def test_cache_uses_function_args_and_kwargs():
    calls = {"count": 0}

    @ttl_cache(ttl_seconds=0.5)
    def compute(a, b=0):
        calls["count"] += 1
        return a + b

    assert compute(2, b=3) == 5
    assert compute(2, b=3) == 5
    assert calls["count"] == 1


def test_invalid_ttl_raises_value_error():
    with pytest.raises(ValueError):
        ttl_cache(ttl_seconds=0)

    with pytest.raises(ValueError):
        ttl_cache(ttl_seconds=-1)
