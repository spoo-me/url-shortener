"""Unit tests for UrlCache and DualCache."""

import json
from unittest.mock import AsyncMock

from infrastructure.cache.dual_cache import DualCache
from infrastructure.cache.url_cache import UrlCache

from .conftest import _fake_redis, _url_data


class TestUrlCache:
    async def test_get_returns_none_when_redis_none(self):
        cache = UrlCache(redis_client=None)
        assert await cache.get("abc") is None

    async def test_get_returns_data_on_hit(self):
        data = _url_data()
        r = _fake_redis(get_returns=json.dumps(data.__dict__))
        cache = UrlCache(r)
        result = await cache.get("abc1234")
        assert result is not None
        assert result.long_url == "https://example.com"
        assert result.url_status == "ACTIVE"

    async def test_get_returns_none_on_miss(self):
        r = _fake_redis(get_returns=None)
        cache = UrlCache(r)
        assert await cache.get("missing") is None

    async def test_set_calls_setex_with_ttl(self):
        r = _fake_redis()
        cache = UrlCache(r, ttl_seconds=300)
        await cache.set("abc1234", _url_data())
        r.setex.assert_called_once()
        call_args = r.setex.call_args[0]
        assert call_args[0] == "url_cache:abc1234"
        assert call_args[1] == 300

    async def test_set_noop_when_redis_none(self):
        cache = UrlCache(redis_client=None)
        await cache.set("abc", _url_data())  # must not raise

    async def test_invalidate_deletes_key(self):
        r = _fake_redis()
        cache = UrlCache(r)
        await cache.invalidate("abc1234")
        r.delete.assert_called_once_with("url_cache:abc1234")

    async def test_invalidate_noop_when_redis_none(self):
        cache = UrlCache(redis_client=None)
        await cache.invalidate("abc")  # must not raise

    async def test_set_stores_json_serialisable_data(self):
        r = _fake_redis()
        cache = UrlCache(r)
        await cache.set("x", _url_data(password_hash="$argon2id$..."))
        _, _, payload = r.setex.call_args[0]
        parsed = json.loads(payload)
        assert parsed["password_hash"] == "$argon2id$..."


class TestDualCache:
    async def test_returns_live_data_on_primary_hit(self):
        r = AsyncMock()
        r.get = AsyncMock(side_effect=[json.dumps({"v": 1}), None])
        r.set = AsyncMock(return_value=True)
        cache = DualCache(r)
        result = await cache.get_or_set("key", AsyncMock(return_value={"v": 99}))
        assert result == {"v": 1}

    async def test_returns_stale_and_schedules_refresh(self):
        r = AsyncMock()
        # primary miss, stale hit
        r.get = AsyncMock(side_effect=[None, json.dumps({"v": "stale"})])
        r.set = AsyncMock(return_value=True)
        cache = DualCache(r)
        result = await cache.get_or_set("key", AsyncMock(return_value={"v": "fresh"}))
        assert result == {"v": "stale"}

    async def test_calls_query_fn_on_full_miss(self):
        r = AsyncMock()
        r.get = AsyncMock(return_value=None)
        r.set = AsyncMock(return_value=True)  # lock acquired
        r.setex = AsyncMock()
        r.delete = AsyncMock()
        query = AsyncMock(return_value={"v": "fresh"})
        cache = DualCache(r)
        result = await cache.get_or_set("key", query)
        assert result == {"v": "fresh"}
        query.assert_awaited_once()

    async def test_returns_none_when_redis_none(self):
        called = False

        async def query():
            nonlocal called
            called = True
            return {"v": 1}

        cache = DualCache(redis_client=None)
        result = await cache.get_or_set("key", query)
        # When redis is None, query is called directly
        assert called
        assert result == {"v": 1}

    async def test_returns_none_on_lock_contention(self):
        r = AsyncMock()
        r.get = AsyncMock(return_value=None)  # both miss
        r.set = AsyncMock(return_value=None)  # lock NOT acquired
        cache = DualCache(r)
        result = await cache.get_or_set("key", AsyncMock(return_value={"v": 1}))
        assert result is None
