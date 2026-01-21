import json
import threading
import time
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

        # Use provided TTLs or fall back to instance defaults
        primary_ttl = primary_ttl if primary_ttl is not None else self.primary_ttl
        stale_ttl = stale_ttl if stale_ttl is not None else self.stale_ttl

        primary_key = f"{base_key}:live"
        stale_key = f"{base_key}:stale"
        lock_key = f"{base_key}:lock"

        # 1. Check primary
        raw = self.get(primary_key)
        if raw:
            return deserialize(raw)

        # 2. Check stale
        stale = self.get(stale_key)
        if stale:
            if self._lock(lock_key):
                self._run_in_thread(
                    lambda: self._refresh(
                        base_key, query_fn, serializer_fn, primary_ttl, stale_ttl
                    )
                )
            return deserialize(stale)

        # 3. No cache — try DB
        if self._lock(lock_key):
            data = query_fn()
            self.set(primary_key, serialize(data), primary_ttl)
            self.set(stale_key, serialize(data), stale_ttl)
            return data

        # 4. Wait and retry
        for _ in range(10):
            time.sleep(0.5)
            raw = self.get(primary_key)
            if raw:
                return deserialize(raw)

        raise Exception(f"Failed to fetch and cache '{base_key}'")

    def _refresh(
        self, base_key, query_fn, serializer_fn=None, primary_ttl=None, stale_ttl=None
    ):
        try:
            data = query_fn()
            serialized = json.dumps(serializer_fn(data) if serializer_fn else data)
            # Use provided TTLs or fall back to instance defaults
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
