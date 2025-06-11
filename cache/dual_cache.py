import json
import threading
import time
from typing import Callable, Any, Optional
from .base_cache import BaseCache


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
    ) -> Any:
        def serialize(data):
            return json.dumps(serializer_fn(data) if serializer_fn else data)

        def deserialize(raw):
            return json.loads(raw)

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
                    lambda: self._refresh(base_key, query_fn, serializer_fn)
                )
            return deserialize(stale)

        # 3. No cache — try DB
        if self._lock(lock_key):
            data = query_fn()
            self.set(primary_key, serialize(data), self.primary_ttl)
            self.set(stale_key, serialize(data), self.stale_ttl)
            return data

        # 4. Wait and retry
        for _ in range(10):
            time.sleep(0.5)
            raw = self.get(primary_key)
            if raw:
                return deserialize(raw)

        raise Exception(f"Failed to fetch and cache '{base_key}'")

    def _refresh(self, base_key, query_fn, serializer_fn=None):
        try:
            data = query_fn()
            serialized = json.dumps(serializer_fn(data) if serializer_fn else data)
            self.set(f"{base_key}:live", serialized, self.primary_ttl)
            self.set(f"{base_key}:stale", serialized, self.stale_ttl)
        except Exception as e:
            print(f"[SmartCache] Refresh error for {base_key}: {e}")
