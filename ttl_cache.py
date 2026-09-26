import functools
import time
from typing import Any, Callable, Dict, Optional, Tuple


class TTLCache:
    """Thread-safe in-memory cache with per-entry TTL expiration."""

    def __init__(self) -> None:
        self._entries: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}

    def _make_key(self, args: tuple, kwargs: dict) -> Tuple[Any, ...]:
        return (args, tuple(sorted(kwargs.items())))

    def get(self, key: Tuple[Any, ...]) -> Optional[Any]:
        entry = self._entries.get(key)
        if entry is None:
            return None

        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._entries[key]
            return None
        return value

    def set(self, key: Tuple[Any, ...], value: Any, ttl_seconds: float) -> None:
        expires_at = time.monotonic() + ttl_seconds
        self._entries[key] = (expires_at, value)

    def clear(self) -> None:
        self._entries.clear()


def ttl_cache(ttl_seconds: float):
    """Decorator that memoizes function results and expires them after ttl_seconds."""
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be greater than 0")

    cache = TTLCache()

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = cache._make_key(args, kwargs)
            cached = cache.get(key)
            if cached is not None:
                return cached

            result = func(*args, **kwargs)
            cache.set(key, result, ttl_seconds)
            return result

        return wrapper

    return decorator
