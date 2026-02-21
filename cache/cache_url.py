from typing import Optional
from dataclasses import dataclass
from .store import CacheStore
from utils.logger import get_logger

log = get_logger(__name__)


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


class UrlCache:
    def __init__(self, store: CacheStore, ttl_seconds: int = 300) -> None:
        self._store = store
        self.ttl_seconds = ttl_seconds

    def set_url_cache_data(self, short_code: str, url_cache_data: UrlCacheData) -> None:
        """Set URL data using the new cache schema"""
        self._store.set(
            f"url_cache:{short_code}", url_cache_data.__dict__, self.ttl_seconds
        )

    def get_url_cache_data(self, short_code: str) -> Optional[UrlCacheData]:
        """Get URL data using the new cache schema"""
        data = self._store.get(f"url_cache:{short_code}")
        return UrlCacheData(**data) if data else None

    def invalidate_url_cache(self, short_code: str) -> None:
        """Invalidate URL cache data"""
        self._store.delete(f"url_cache:{short_code}")
        log.info(
            "cache_invalidated", short_code=short_code, reason="manual_invalidation"
        )
