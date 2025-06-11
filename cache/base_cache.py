from typing import Optional
from redis import Redis
from .redis_client import get_redis


class BaseCache:
    def __init__(self):
        try:
            self.r: Optional[Redis] = get_redis()
        except Exception as e:
            print(f"[BaseCache] Could not initialize Redis: {e}")
            self.r = None

    def get(self, key: str):
        return self.r.get(key) if self.r else None

    def set(self, key: str, value: str, ex: int):
        return self.r.setex(key, ex, value) if self.r else None

    def delete(self, key: str):
        if self.r:
            self.r.delete(key)
