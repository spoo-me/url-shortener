from typing import Optional
from redis import Redis
from .redis_client import get_redis
from utils.logger import get_logger

log = get_logger(__name__)


class BaseCache:
    def __init__(self):
        try:
            self.r: Optional[Redis] = get_redis()
        except Exception as e:
            log.error(
                "redis_initialization_failed", error=str(e), error_type=type(e).__name__
            )
            self.r = None

    def get(self, key: str):
        return self.r.get(key) if self.r else None

    def set(self, key: str, value: str, ex: int):
        return self.r.setex(key, ex, value) if self.r else None

    def delete(self, key: str):
        if self.r:
            self.r.delete(key)
