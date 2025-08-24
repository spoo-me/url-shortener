import json
from typing import Optional
from dataclasses import dataclass
from .base_cache import BaseCache
from redis.exceptions import RedisError
import warnings


@dataclass
class UrlData:
    warnings.warn(
        "[UrlCache] UrlData is deprecated, use UrlCacheData instead",
        DeprecationWarning,
        stacklevel=2,
    )
    url: str
    short_code: str
    password: Optional[str]
    block_bots: bool


@dataclass
class UrlCacheData:
    """New cache schema for both old and new URL schemas"""

    _id: str  # MongoDB ObjectId as string
    alias: str
    long_url: str
    block_bots: bool
    password_hash: Optional[str]
    expiration_time: Optional[int]  # Unix timestamp
    max_clicks: Optional[int]
    url_status: str  # ACTIVE, INACTIVE, BLOCKED, EXPIRED
    schema_version: str  # "v1" or "v2"
    owner_id: Optional[str]  # MongoDB ObjectId as string, null for v1 URLs


class UrlCache(BaseCache):
    def __init__(self, ttl_seconds: int = 300):
        super().__init__()
        self.ttl_seconds = ttl_seconds

    def set_url_cache_data(self, short_code: str, url_cache_data: UrlCacheData) -> None:
        """Set URL data using the new cache schema"""
        if not self.r:
            return
        try:
            key = f"url_cache:{short_code}"
            self.r.set(key, json.dumps(url_cache_data.__dict__), ex=self.ttl_seconds)
        except RedisError as e:
            print(f"[UrlCache] Redis SET error: {e}")

    def get_url_cache_data(self, short_code: str) -> Optional[UrlCacheData]:
        """Get URL data using the new cache schema"""
        if not self.r:
            return None
        try:
            key = f"url_cache:{short_code}"
            raw = self.r.get(key)
            if not raw:
                return None
            data = json.loads(raw)
            return UrlCacheData(**data)
        except (RedisError, json.JSONDecodeError, TypeError) as e:
            print(f"[UrlCache] Redis GET error: {e}")
            return None

    def invalidate_url_cache(self, short_code: str) -> None:
        """Invalidate URL cache data"""
        if not self.r:
            return
        try:
            key = f"url_cache:{short_code}"
            self.r.delete(key)
        except RedisError as e:
            print(f"[UrlCache] Redis DELETE error: {e}")

    def set_url_data(self, short_code: str, url_data: UrlData) -> None:
        warnings.warn(
            "[UrlCache] set_url_data is deprecated, use set_url_cache_data instead",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self.r:
            return
        try:
            key = f"meta:{short_code}"
            self.r.set(key, json.dumps(url_data.__dict__), ex=self.ttl_seconds)
        except RedisError as e:
            print(f"[UrlCache] Redis SET error: {e}")

    def get_url_data(self, short_code: str) -> Optional[UrlData]:
        warnings.warn(
            "[UrlCache] get_url_data is deprecated, use get_url_cache_data instead",
            DeprecationWarning,
            stacklevel=2,
        )
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
