import json
import threading
from typing import Callable, Any, Optional
from .base_cache import BaseCache
from utils.logger import get_logger

log = get_logger(__name__)


class DualCache(BaseCache):
    def __init__(self, primary_ttl=300, stale_ttl=900, lock_ttl=30):
        super().__init__()
        self.primary_ttl = primary_ttl
        self.stale_ttl = stale_ttl
        self.lock_ttl = lock_ttl

    def _lock(self, key: str) -> bool:
        return self.r and self.r.set(key, "1", nx=True, ex=self.lock_ttl)

    def _run_in_thread(self, fn: Callable):
        thread = threading.Thread(target=fn, daemon=True)
        thread.start()

    def get_or_set(
        self,
        base_key: str,
        query_fn: Callable[[], Any],
        serializer_fn: Optional[Callable[[Any], Any]] = None,
        primary_ttl: Optional[int] = None,
        stale_ttl: Optional[int] = None,
    ) -> Any:
        def serialize(data):
            return json.dumps(serializer_fn(data) if serializer_fn else data)

        def deserialize(raw):
            return json.loads(raw)

        # Use provided TTLs, fall back to instance defaults if not provided
        primary_ttl = primary_ttl if primary_ttl is not None else self.primary_ttl
        stale_ttl = stale_ttl if stale_ttl is not None else self.stale_ttl

        primary_key = f"{base_key}:live"
        stale_key = f"{base_key}:stale"
        lock_key = f"{base_key}:lock"

        # Check primary
        raw = self.get(primary_key)
        if raw:
            return deserialize(raw)

        # Check stale
        stale = self.get(stale_key)
        if stale:
            if self._lock(lock_key):
                self._run_in_thread(
                    lambda: self._refresh(
                        base_key, query_fn, serializer_fn, primary_ttl, stale_ttl
                    )
                )
            return deserialize(stale)

        # No cache, try DB
        if self._lock(lock_key):
            try:
                data = query_fn()
                self.set(primary_key, serialize(data), primary_ttl)
                self.set(stale_key, serialize(data), stale_ttl)
                self.delete(lock_key)
                return data
            except Exception as e:
                log.error(
                    "dual_cache_query_failed",
                    base_key=base_key,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                return None
                # lock intentionally not released on failure — expires after
                # lock_ttl to rate-limit retries while the query is broken

        # Lock contention — another worker is already fetching.
        # Return None immediately; caller should respond with 204 No Content.
        log.debug("dual_cache_lock_contention", base_key=base_key)
        return None

    def _refresh(
        self, base_key, query_fn, serializer_fn=None, primary_ttl=None, stale_ttl=None
    ):
        try:
            data = query_fn()
            serialized = json.dumps(serializer_fn(data) if serializer_fn else data)
            # Use provided TTLs, fall back to instance defaults if not provided
            primary_ttl = primary_ttl if primary_ttl is not None else self.primary_ttl
            stale_ttl = stale_ttl if stale_ttl is not None else self.stale_ttl
            self.set(f"{base_key}:live", serialized, primary_ttl)
            self.set(f"{base_key}:stale", serialized, stale_ttl)
        except Exception as e:
            log.error(
                "cache_refresh_failed",
                base_key=base_key,
                error=str(e),
                error_type=type(e).__name__,
            )
