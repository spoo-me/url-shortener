"""Tests for the async Redis connection factory."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import RedisError

from app.infrastructure.cache.redis_client import create_redis_client


def _patched_from_url(client: AsyncMock):
    return patch(
        "app.infrastructure.cache.redis_client.aioredis.from_url",
        return_value=client,
    )


class TestCreateRedisClient:
    async def test_returns_client_when_ping_succeeds(self):
        client = AsyncMock()
        with _patched_from_url(client):
            assert await create_redis_client("redis://x:6379/0") is client
        client.aclose.assert_not_awaited()

    async def test_closes_client_when_ping_fails(self):
        """A failed ping must not leak the constructed connection pool."""
        client = AsyncMock()
        client.ping.side_effect = RedisError("down")
        with _patched_from_url(client):
            assert await create_redis_client("redis://x:6379/0") is None
        client.aclose.assert_awaited_once()

    async def test_closes_client_on_unexpected_ping_error(self):
        client = AsyncMock()
        client.ping.side_effect = OSError("wedged socket")
        with _patched_from_url(client):
            assert await create_redis_client("redis://x:6379/0") is None
        client.aclose.assert_awaited_once()

    async def test_returns_none_when_construction_fails(self):
        with patch(
            "app.infrastructure.cache.redis_client.aioredis.from_url",
            side_effect=ValueError("bad uri"),
        ):
            assert await create_redis_client("not-a-uri") is None

    async def test_sets_bounded_socket_timeouts(self):
        """A wedged connection must raise, not hang the redirect path."""
        client = AsyncMock()
        with _patched_from_url(client) as from_url:
            await create_redis_client("redis://x:6379/0")
        kwargs = from_url.call_args.kwargs
        assert kwargs["socket_timeout"] == 5
        assert kwargs["socket_connect_timeout"] == 5


class TestCreateCacheClient:
    async def test_wedged_redis_fails_fast_instead_of_hanging(self):
        """A Redis that accepts the connection but never answers (paused,
        overloaded, half-open) must raise quickly so the cache can miss."""
        import asyncio
        import socket
        import time

        from app.infrastructure.cache.redis_client import create_cache_client

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(8)
        client = create_cache_client(f"redis://127.0.0.1:{sock.getsockname()[1]}/0")
        start = time.monotonic()
        try:
            with pytest.raises(RedisError):
                await asyncio.wait_for(client.get("k"), timeout=10)
        finally:
            await client.aclose()
            sock.close()
        assert time.monotonic() - start < 2
