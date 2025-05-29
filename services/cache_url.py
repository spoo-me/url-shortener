import redis
from typing import Optional
from dataclasses import dataclass
from redis.exceptions import RedisError
import json


@dataclass
class urlData:
    url: str
    short_code: str
    password: Optional[str]
    block_bots: bool


class cache_query:
    def __init__(self, redis_uri: Optional[str], ttl_seconds: int = 60 * 5) -> None:
        self.r: Optional[redis.Redis] = None
        self.ttl_seconds: int = ttl_seconds

        if not redis_uri:
            print("[RedisCache] No Redis URI provided. Caching is disabled.")
            return

        try:
            self.r = redis.Redis.from_url(redis_uri)
            self.r.ping()  # test connection
            print("[RedisCache] Connected to Redis.")
        except RedisError as e:
            print(f"[RedisCache] Failed to connect to Redis: {e}")
            self.r = None

    def set_url_data(self, short_code: str, url_data: urlData) -> None:
        if not self.r:
            return
        try:
            self.r.set(
                f"meta:{short_code}", json.dumps(url_data.__dict__), ex=self.ttl_seconds
            )
        except RedisError as e:
            print(f"[RedisCache] Redis SET error: {e}")

    def get_url_data(self, short_code: str) -> Optional[urlData]:
        if not self.r:
            return None
        try:
            raw = self.r.get(f"meta:{short_code}")
            if not raw:
                return None
            data = json.loads(raw)
            return urlData(**data)
        except (RedisError, json.JSONDecodeError, TypeError) as e:
            print(f"[RedisCache] Redis GET error: {e}")
            return None
