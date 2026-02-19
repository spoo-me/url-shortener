import functools
import hashlib
import json
from typing import Any, Optional
from walrus import Cache
from utils.logger import get_logger

log = get_logger(__name__)


class CacheStore:
    """
    Central cache abstraction wrapping walrus.Cache.

    Provides a @cached decorator for transparent function-level caching,
    and safe get/set/delete methods that never raise — cache failures log
    and degrade gracefully without crashing the app.
    """

    def __init__(self, cache: Cache) -> None:
        self._cache = cache

    def cached(self, key: str, ttl: int):
        """
        Decorator that caches a function's return value in Redis.

        On hit  : returns the cached value without calling the function.
        On miss : calls the function, stores the result, returns it.
        On error: falls back to calling the function directly.
        """

        def decorator(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                try:
                    if args or kwargs:
                        args_hash = hashlib.md5(
                            json.dumps(
                                (args, sorted(kwargs.items())),
                                default=str,
                            ).encode()
                        ).hexdigest()[:8]
                        cache_key = f"{key}:{args_hash}"
                    else:
                        cache_key = key
                    result = self._cache.get(cache_key)
                    if result is not None:
                        return result
                    result = fn(*args, **kwargs)
                    self._cache.set(cache_key, result, ttl)
                    return result
                except Exception:
                    return fn(*args, **kwargs)

            return wrapper

        return decorator

    def get(self, key: str) -> Optional[Any]:
        try:
            return self._cache.get(key)
        except Exception as e:
            log.error(
                "cache_get_failed", key=key, error=str(e), error_type=type(e).__name__
            )
            return None

    def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            self._cache.set(key, value, ttl)
        except Exception as e:
            log.error(
                "cache_set_failed", key=key, error=str(e), error_type=type(e).__name__
            )

    def delete(self, key: str) -> None:
        try:
            self._cache.delete(key)
        except Exception as e:
            log.error(
                "cache_delete_failed",
                key=key,
                error=str(e),
                error_type=type(e).__name__,
            )
