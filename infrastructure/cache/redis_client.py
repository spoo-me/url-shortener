"""Async Redis connection factory.

Returns an async redis.Redis client, or None if Redis is not configured
or the connection fails. All callers must handle the None case gracefully.
"""

from typing import Optional

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from shared.logging import get_logger

log = get_logger(__name__)


async def create_redis_client(redis_uri: str) -> Optional[aioredis.Redis]:
    """Connect to Redis and return a client, or None on failure."""
    try:
        client: aioredis.Redis = aioredis.from_url(redis_uri, decode_responses=True)
        await client.ping()
        log.info("redis_connected", uri=redis_uri.split("@")[-1])  # mask credentials
        return client
    except RedisError as e:
        log.warning(
            "redis_connection_failed", error=str(e), error_type=type(e).__name__
        )
        return None
    except Exception as e:
        log.warning("redis_unexpected_error", error=str(e), error_type=type(e).__name__)
        return None
