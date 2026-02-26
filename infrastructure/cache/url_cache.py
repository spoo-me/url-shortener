"""URL-specific Redis cache.

Stores UrlCacheData as JSON (not pickle) so cache entries are
debuggable and safe to deserialise across Python versions.
"""

import json
from dataclasses import asdict, dataclass
from typing import Optional

import redis.asyncio as aioredis

from shared.logging import get_logger

log = get_logger(__name__)


@dataclass
class UrlCacheData:
    """Unified cache schema covering both v1 (legacy) and v2 URLs."""

    _id: str  # MongoDB ObjectId as string
    alias: str
    long_url: str
    block_bots: bool
    password_hash: Optional[str]
    expiration_time: Optional[int]  # Unix timestamp
    max_clicks: Optional[int]
    url_status: str  # ACTIVE, INACTIVE, BLOCKED, EXPIRED
    schema_version: str  # "v1" or "v2"
    owner_id: Optional[str]  # ObjectId as string; None for v1 URLs


class UrlCache:
    def __init__(
        self, redis_client: Optional[aioredis.Redis], ttl_seconds: int = 300
    ) -> None:
        self._redis = redis_client
        self.ttl_seconds = ttl_seconds

    def _key(self, short_code: str) -> str:
        return f"url_cache:{short_code}"

    async def get(self, short_code: str) -> Optional[UrlCacheData]:
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(self._key(short_code))
            if raw is None:
                return None
            return UrlCacheData(**json.loads(raw))
        except Exception as e:
            log.warning("url_cache_get_error", short_code=short_code, error=str(e))
            return None

    async def set(self, short_code: str, data: UrlCacheData) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.setex(
                self._key(short_code),
                self.ttl_seconds,
                json.dumps(asdict(data)),
            )
        except Exception as e:
            log.error("url_cache_set_error", short_code=short_code, error=str(e))

    async def invalidate(self, short_code: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.delete(self._key(short_code))
            log.info(
                "cache_invalidated", short_code=short_code, reason="manual_invalidation"
            )
        except Exception as e:
            log.error("url_cache_invalidate_error", short_code=short_code, error=str(e))
