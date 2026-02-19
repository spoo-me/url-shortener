import functools
import hashlib
import json
from typing import Any, Optional
from walrus import Cache
from .redis_client import get_cache
from utils.logger import get_logger

log = get_logger(__name__)

_MISS = object()  # sentinel to distinguish a cache miss from a cached None


class CacheStore:
    """
    Key-value cache backed by Redis (walrus.Cache).

    Provides a @cached decorator for transparent function-level caching,
    and safe get/set/delete methods that never raise — all operations
    degrade to no-ops if Redis is unavailable.
    """

    def __init__(self) -> None:
        self._cache: Optional[Cache] = get_cache()
        if self._cache is None:
            log.warning("cache_store_unavailable")

    def cached(self, key: str, ttl: int):
        """
        Decorator that caches a function's return value in Redis.

        Incorporates function arguments into the cache key so parameterised
        functions are safe to decorate.

        On hit  : returns the cached value without calling the function.
        On miss : calls the function, stores the result, returns it.
        On miss (Redis unavailable): calls the function directly.
        """

        def decorator(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                if not self._cache:
                    return fn(*args, **kwargs)
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
                    result = self._cache.get(cache_key, default=_MISS)
                    if result is not _MISS:
                        return result
                    result = fn(*args, **kwargs)
                    self._cache.set(cache_key, result, ttl)
                    return result
                except Exception as e:
                    log.error(
                        "cache_decorated_call_failed",
                        key=key,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    return fn(*args, **kwargs)

            return wrapper

        return decorator

    def get(self, key: str) -> Optional[Any]:
        if not self._cache:
            return None
        try:
            return self._cache.get(key)
        except Exception as e:
            log.error(
                "cache_get_failed", key=key, error=str(e), error_type=type(e).__name__
            )
            return None

    def set(self, key: str, value: Any, ttl: int) -> None:
        if not self._cache:
            return
        try:
            self._cache.set(key, value, ttl)
        except Exception as e:
            log.error(
                "cache_set_failed", key=key, error=str(e), error_type=type(e).__name__
            )

    def delete(self, key: str) -> None:
        if not self._cache:
            return
        try:
            self._cache.delete(key)
        except Exception as e:
            log.error(
                "cache_delete_failed",
                key=key,
                error=str(e),
                error_type=type(e).__name__,
            )
