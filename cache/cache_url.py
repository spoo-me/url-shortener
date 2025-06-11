import json
from typing import Optional
from dataclasses import dataclass
from .base_cache import BaseCache
from redis.exceptions import RedisError


@dataclass
class UrlData:
    url: str
    short_code: str
    password: Optional[str]
    block_bots: bool


class UrlCache(BaseCache):
    def __init__(self, ttl_seconds: int = 300):
        super().__init__()
        self.ttl_seconds = ttl_seconds

    def set_url_data(self, short_code: str, url_data: UrlData) -> None:
        if not self.r:
            return
        try:
            key = f"meta:{short_code}"
            self.r.set(key, json.dumps(url_data.__dict__), ex=self.ttl_seconds)
        except RedisError as e:
            print(f"[UrlCache] Redis SET error: {e}")

    def get_url_data(self, short_code: str) -> Optional[UrlData]:
        if not self.r:
            return None
        try:
            key = f"meta:{short_code}"
            raw = self.r.get(key)
            if not raw:
                return None
            data = json.loads(raw)
            return UrlData(**data)
        except (RedisError, json.JSONDecodeError, TypeError) as e:
            print(f"[UrlCache] Redis GET error: {e}")
            return None
