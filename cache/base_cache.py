from typing import Any, Optional
from walrus import Database
from .redis_client import get_redis
from utils.logger import get_logger

log = get_logger(__name__)


class BaseCache:
    def __init__(self):
        self.r: Optional[Database] = get_redis()
        if self.r is None:
            log.warning("base_cache_unavailable")

    def get(self, key: str) -> Optional[Any]:
        return self.r.get(key) if self.r else None

    def set(self, key: str, value: Any, ttl: int) -> None:
        if self.r:
            self.r.setex(key, ttl, value)

    def delete(self, key: str) -> None:
        if self.r:
            self.r.delete(key)
