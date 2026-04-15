"""URL-specific Redis cache.

Stores UrlCacheData as JSON (not pickle) so cache entries are
debuggable and safe to deserialise across Python versions.
"""

import redis.asyncio as aioredis
from pydantic import BaseModel, ConfigDict, Field

from shared.crypto import verify_password as verify_password_hash
from shared.logging import get_logger

log = get_logger(__name__)


class UrlCacheData(BaseModel):
    """Unified cache schema covering both v1 (legacy) and v2 URLs."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")  # accepts "_id" from cached JSON, stored as "id"
    alias: str
    long_url: str
    block_bots: bool
    password_hash: str | None
    expiration_time: int | None  # Unix timestamp
    max_clicks: int | None
    url_status: str  # ACTIVE, INACTIVE, BLOCKED, EXPIRED
    schema_version: str  # "v1" or "v2"
    owner_id: str | None  # ObjectId as string; None for v1 URLs
    total_clicks: int = 0  # Live click count for v1 max-clicks check

    def verify_password(self, password: str | None) -> bool:
        """Check a password against this URL's stored hash.

        Handles schema-specific hashing: argon2 for v2, plaintext for v1/emoji.
        Returns True if no password is set or if the password matches.
        """
        if not self.password_hash:
            return True
        if password is None:
            return False
        if self.schema_version == "v2":
            return verify_password_hash(password, self.password_hash)
        return password == self.password_hash


class UrlCache:
    def __init__(
        self, redis_client: aioredis.Redis | None, ttl_seconds: int = 300
    ) -> None:
        self._redis = redis_client
        self.ttl_seconds = ttl_seconds

    def _key(self, short_code: str) -> str:
        return f"url_cache:{short_code}"

    async def get(self, short_code: str) -> UrlCacheData | None:
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(self._key(short_code))
            if raw is None:
                return None
            return UrlCacheData.model_validate_json(raw)
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
                data.model_dump_json(by_alias=True),
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
