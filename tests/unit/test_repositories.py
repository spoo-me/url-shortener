"""
Unit tests for Phase 6 repositories.

All MongoDB collections are replaced with AsyncMock so no real DB is needed.
Tests verify:
- Each method calls the correct collection operation with the right arguments.
- find_by_* methods return None when the collection returns None.
- insert methods return the inserted ID.
- ensure_indexes() calls create_index with correct field specs.
- Legacy repositories pass update documents through unchanged.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from bson import ObjectId


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def make_cursor() -> AsyncMock:
    """Return a mock async cursor that supports chaining and to_list()."""
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[])
    return cursor


def make_collection() -> AsyncMock:
    """Return a mock that behaves like an async pymongo AsyncCollection.

    In PyMongo async, find() and aggregate() are *synchronous* calls that
    return a cursor object; only cursor.to_list() is awaitable. We reflect
    that here by using MagicMock (not AsyncMock) for find/aggregate so that
    calling them returns a cursor directly rather than a coroutine.
    """
    col = AsyncMock()
    cursor = make_cursor()
    col.find = MagicMock(return_value=cursor)
    col.aggregate = MagicMock(return_value=cursor)
    return col


USER_OID = ObjectId("aaaaaaaaaaaaaaaaaaaaaaaa")
URL_OID = ObjectId("bbbbbbbbbbbbbbbbbbbbbbbb")
KEY_OID = ObjectId("cccccccccccccccccccccccc")
TOKEN_OID = ObjectId("dddddddddddddddddddddddd")


def _url_v2_doc():
    return {
        "_id": URL_OID,
        "alias": "abc1234",
        "owner_id": USER_OID,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "creation_ip": "1.2.3.4",
        "long_url": "https://example.com",
        "password": None,
        "block_bots": None,
        "max_clicks": None,
        "expire_after": None,
        "status": "ACTIVE",
        "private_stats": True,
        "total_clicks": 0,
        "last_click": None,
    }


def _api_key_doc():
    return {
        "_id": KEY_OID,
        "user_id": USER_OID,
        "token_prefix": "spoo_abc",
        "token_hash": "deadbeef" * 8,
        "name": "My Key",
        "scopes": ["urls:read"],
        "revoked": False,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }


def _token_doc():
    return {
        "_id": TOKEN_OID,
        "user_id": USER_OID,
        "email": "user@example.com",
        "token_hash": "cafebabe" * 8,
        "token_type": "email_verify",
        "expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "used_at": None,
        "attempts": 0,
    }


def _legacy_url_doc():
    return {
        "_id": "abc123",
        "url": "https://example.com",
        "password": None,
        "max-clicks": None,
        "total-clicks": 0,
        "block-bots": None,
        "expiration-time": None,
        "last-click": None,
        "last-click-browser": None,
        "last-click-os": None,
        "last-click-country": None,
        "ips": [],
        "counter": {},
        "unique_counter": {},
        "country": {},
        "browser": {},
        "os_name": {},
        "referrer": {},
        "bots": {},
        "average_redirection_time": 0.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# UrlRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestUrlRepository:
    def _repo(self, col=None):
        from repositories.url_repository import UrlRepository

        return UrlRepository(col or make_collection())

    @pytest.mark.asyncio
    async def test_find_by_alias_returns_model(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=_url_v2_doc())
        result = await self._repo(col).find_by_alias("abc1234")
        col.find_one.assert_awaited_once_with({"alias": "abc1234"})
        assert result is not None
        assert result.alias == "abc1234"

    @pytest.mark.asyncio
    async def test_find_by_alias_returns_none_on_miss(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=None)
        result = await self._repo(col).find_by_alias("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_id_returns_model(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=_url_v2_doc())
        result = await self._repo(col).find_by_id(URL_OID)
        col.find_one.assert_awaited_once_with({"_id": URL_OID})
        assert result is not None

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none_on_miss(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=None)
        assert await self._repo(col).find_by_id(URL_OID) is None

    @pytest.mark.asyncio
    async def test_insert_returns_id(self):
        col = make_collection()
        result_mock = MagicMock()
        result_mock.inserted_id = URL_OID
        col.insert_one = AsyncMock(return_value=result_mock)
        doc = {"alias": "abc1234", "long_url": "https://example.com"}
        oid = await self._repo(col).insert(doc)
        col.insert_one.assert_awaited_once_with(doc)
        assert oid == URL_OID

    @pytest.mark.asyncio
    async def test_update_returns_true_on_match(self):
        col = make_collection()
        result_mock = MagicMock(matched_count=1)
        col.update_one = AsyncMock(return_value=result_mock)
        ops = {"$set": {"status": "INACTIVE"}}
        ok = await self._repo(col).update(URL_OID, ops)
        col.update_one.assert_awaited_once_with({"_id": URL_OID}, ops)
        assert ok is True

    @pytest.mark.asyncio
    async def test_update_returns_false_on_no_match(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock(matched_count=0))
        ok = await self._repo(col).update(URL_OID, {"$set": {"status": "INACTIVE"}})
        assert ok is False

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_deleted(self):
        col = make_collection()
        col.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
        ok = await self._repo(col).delete(URL_OID)
        col.delete_one.assert_awaited_once_with({"_id": URL_OID})
        assert ok is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self):
        col = make_collection()
        col.delete_one = AsyncMock(return_value=MagicMock(deleted_count=0))
        assert await self._repo(col).delete(URL_OID) is False

    @pytest.mark.asyncio
    async def test_check_alias_exists_true(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value={"_id": URL_OID})
        assert await self._repo(col).check_alias_exists("abc1234") is True
        col.find_one.assert_awaited_once_with({"alias": "abc1234"}, {"_id": 1})

    @pytest.mark.asyncio
    async def test_check_alias_exists_false(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=None)
        assert await self._repo(col).check_alias_exists("nope") is False

    @pytest.mark.asyncio
    async def test_increment_clicks_uses_inc_and_set(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock())
        ts = datetime(2024, 6, 1, tzinfo=timezone.utc)
        await self._repo(col).increment_clicks(URL_OID, last_click_time=ts)
        col.update_one.assert_awaited_once_with(
            {"_id": URL_OID},
            {"$inc": {"total_clicks": 1}, "$set": {"last_click": ts}},
        )

    @pytest.mark.asyncio
    async def test_increment_clicks_uses_now_when_no_time(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock())
        await self._repo(col).increment_clicks(URL_OID)
        args = col.update_one.call_args
        update_doc = args[0][1]
        assert "$set" in update_doc
        assert isinstance(update_doc["$set"]["last_click"], datetime)

    @pytest.mark.asyncio
    async def test_expire_if_max_clicks_returns_true_when_expired(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        result = await self._repo(col).expire_if_max_clicks(URL_OID, 100)
        col.update_one.assert_awaited_once_with(
            {"_id": URL_OID, "total_clicks": {"$gte": 100}},
            {"$set": {"status": "EXPIRED"}},
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_expire_if_max_clicks_returns_false_when_not_reached(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock(modified_count=0))
        assert await self._repo(col).expire_if_max_clicks(URL_OID, 100) is False

    @pytest.mark.asyncio
    async def test_find_by_owner_returns_models(self):
        col = make_collection()
        cursor = col.find.return_value
        cursor.to_list = AsyncMock(return_value=[_url_v2_doc()])
        query = {"owner_id": USER_OID}
        from schemas.models.url import UrlV2Doc

        docs = await self._repo(col).find_by_owner(query, "created_at", -1, 0, 20)
        col.find.assert_called_once_with(query)
        cursor.sort.assert_called_once_with("created_at", -1)
        cursor.sort.return_value.skip.assert_called_once_with(0)
        assert len(docs) == 1
        assert isinstance(docs[0], UrlV2Doc)

    @pytest.mark.asyncio
    async def test_count_by_query(self):
        col = make_collection()
        col.count_documents = AsyncMock(return_value=42)
        count = await self._repo(col).count_by_query({"owner_id": USER_OID})
        col.count_documents.assert_awaited_once_with({"owner_id": USER_OID})
        assert count == 42

    @pytest.mark.asyncio
    async def test_raises_on_db_error(self):
        col = make_collection()
        col.find_one = AsyncMock(side_effect=Exception("connection refused"))
        with pytest.raises(Exception, match="connection refused"):
            await self._repo(col).find_by_alias("any")


# ─────────────────────────────────────────────────────────────────────────────
# ClickRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestClickRepository:
    def _repo(self, col=None):
        from repositories.click_repository import ClickRepository

        return ClickRepository(col or make_collection())

    @pytest.mark.asyncio
    async def test_insert_calls_insert_one(self):
        col = make_collection()
        col.insert_one = AsyncMock(return_value=MagicMock())
        doc = {
            "meta": {"url_id": URL_OID, "short_code": "abc1234", "owner_id": USER_OID},
            "clicked_at": datetime.now(timezone.utc),
            "browser": "Chrome",
        }
        result = await self._repo(col).insert(doc)
        col.insert_one.assert_awaited_once_with(doc)
        assert result is None

    @pytest.mark.asyncio
    async def test_insert_raises_on_db_error(self):
        col = make_collection()
        col.insert_one = AsyncMock(side_effect=Exception("write error"))
        with pytest.raises(Exception, match="write error"):
            await self._repo(col).insert(
                {"meta": {}, "clicked_at": datetime.now(timezone.utc)}
            )

    @pytest.mark.asyncio
    async def test_aggregate_returns_list(self):
        col = make_collection()
        cursor = col.aggregate.return_value
        cursor.to_list = AsyncMock(return_value=[{"result": 1}])
        pipeline = [{"$match": {"meta.url_id": URL_OID}}]
        result = await self._repo(col).aggregate(pipeline)
        col.aggregate.assert_called_once_with(pipeline)
        assert result == [{"result": 1}]

    @pytest.mark.asyncio
    async def test_aggregate_raises_on_db_error(self):
        col = make_collection()
        cursor = col.aggregate.return_value
        cursor.to_list = AsyncMock(side_effect=Exception("agg failed"))
        with pytest.raises(Exception, match="agg failed"):
            await self._repo(col).aggregate([])


# ─────────────────────────────────────────────────────────────────────────────
# UserRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestUserRepository:
    def _repo(self, col=None):
        from repositories.user_repository import UserRepository

        return UserRepository(col or make_collection())

    def _user_doc(self):
        return {
            "_id": USER_OID,
            "email": "test@example.com",
            "email_verified": True,
            "password_hash": None,
            "password_set": False,
            "auth_providers": [],
            "plan": "free",
            "status": "ACTIVE",
        }

    @pytest.mark.asyncio
    async def test_find_by_email_returns_model(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=self._user_doc())
        result = await self._repo(col).find_by_email("test@example.com")
        col.find_one.assert_awaited_once_with({"email": "test@example.com"})
        assert result is not None
        assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_find_by_email_returns_none_on_miss(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=None)
        assert await self._repo(col).find_by_email("nope@example.com") is None

    @pytest.mark.asyncio
    async def test_find_by_id_returns_model(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=self._user_doc())
        result = await self._repo(col).find_by_id(USER_OID)
        col.find_one.assert_awaited_once_with({"_id": USER_OID})
        assert result is not None

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none_on_miss(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=None)
        assert await self._repo(col).find_by_id(USER_OID) is None

    @pytest.mark.asyncio
    async def test_find_by_oauth_provider(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=self._user_doc())
        result = await self._repo(col).find_by_oauth_provider(
            "google", "google-uid-123"
        )
        col.find_one.assert_awaited_once_with(
            {
                "auth_providers.provider": "google",
                "auth_providers.provider_user_id": "google-uid-123",
            }
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_find_by_oauth_provider_returns_none(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=None)
        assert await self._repo(col).find_by_oauth_provider("github", "uid") is None

    @pytest.mark.asyncio
    async def test_create_returns_inserted_id(self):
        col = make_collection()
        mock_result = MagicMock(inserted_id=USER_OID)
        col.insert_one = AsyncMock(return_value=mock_result)
        user_data = {"email": "new@example.com"}
        oid = await self._repo(col).create(user_data)
        col.insert_one.assert_awaited_once_with(user_data)
        assert oid == USER_OID

    @pytest.mark.asyncio
    async def test_update_returns_true_on_match(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
        ops = {"$set": {"email_verified": True}}
        ok = await self._repo(col).update(USER_OID, ops)
        col.update_one.assert_awaited_once_with({"_id": USER_OID}, ops)
        assert ok is True

    @pytest.mark.asyncio
    async def test_update_returns_false_on_no_match(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock(matched_count=0))
        assert await self._repo(col).update(USER_OID, {"$set": {}}) is False

    @pytest.mark.asyncio
    async def test_raises_on_db_error(self):
        col = make_collection()
        col.find_one = AsyncMock(side_effect=RuntimeError("network error"))
        with pytest.raises(RuntimeError, match="network error"):
            await self._repo(col).find_by_email("test@example.com")


# ─────────────────────────────────────────────────────────────────────────────
# ApiKeyRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestApiKeyRepository:
    def _repo(self, col=None):
        from repositories.api_key_repository import ApiKeyRepository

        return ApiKeyRepository(col or make_collection())

    @pytest.mark.asyncio
    async def test_insert_returns_id(self):
        col = make_collection()
        col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=KEY_OID))
        oid = await self._repo(col).insert({"token_hash": "abc", "user_id": USER_OID})
        assert oid == KEY_OID

    @pytest.mark.asyncio
    async def test_find_by_hash_returns_model(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=_api_key_doc())
        result = await self._repo(col).find_by_hash("deadbeef" * 8)
        col.find_one.assert_awaited_once_with({"token_hash": "deadbeef" * 8})
        assert result is not None
        assert result.revoked is False

    @pytest.mark.asyncio
    async def test_find_by_hash_returns_none(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=None)
        assert await self._repo(col).find_by_hash("nope") is None

    @pytest.mark.asyncio
    async def test_list_by_user_returns_models(self):
        col = make_collection()
        cursor = col.find.return_value
        cursor.sort.return_value = cursor
        cursor.to_list = AsyncMock(return_value=[_api_key_doc()])
        result = await self._repo(col).list_by_user(USER_OID)
        col.find.assert_called_once_with({"user_id": USER_OID})
        cursor.sort.assert_called_once_with("created_at", 1)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_revoke_soft(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        result = await self._repo(col).revoke(USER_OID, KEY_OID, hard_delete=False)
        col.update_one.assert_awaited_once_with(
            {"_id": KEY_OID, "user_id": USER_OID},
            {"$set": {"revoked": True}},
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_hard_delete(self):
        col = make_collection()
        col.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
        result = await self._repo(col).revoke(USER_OID, KEY_OID, hard_delete=True)
        col.delete_one.assert_awaited_once_with({"_id": KEY_OID, "user_id": USER_OID})
        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_returns_false_on_not_found(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock(modified_count=0))
        assert await self._repo(col).revoke(USER_OID, KEY_OID) is False

    @pytest.mark.asyncio
    async def test_count_by_user(self):
        col = make_collection()
        col.count_documents = AsyncMock(return_value=3)
        count = await self._repo(col).count_by_user(USER_OID)
        col.count_documents.assert_awaited_once_with(
            {"user_id": USER_OID, "revoked": {"$ne": True}}
        )
        assert count == 3


# ─────────────────────────────────────────────────────────────────────────────
# TokenRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestTokenRepository:
    def _repo(self, col=None):
        from repositories.token_repository import TokenRepository

        return TokenRepository(col or make_collection())

    @pytest.mark.asyncio
    async def test_create_returns_id(self):
        col = make_collection()
        col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=TOKEN_OID))
        oid = await self._repo(col).create({"token_hash": "abc"})
        assert oid == TOKEN_OID

    @pytest.mark.asyncio
    async def test_find_by_hash_queries_unused_token(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=_token_doc())
        result = await self._repo(col).find_by_hash("cafebabe" * 8, "email_verify")
        col.find_one.assert_awaited_once_with(
            {
                "token_hash": "cafebabe" * 8,
                "token_type": "email_verify",
                "used_at": None,
            }
        )
        assert result is not None
        assert result.token_type == "email_verify"

    @pytest.mark.asyncio
    async def test_find_by_hash_returns_none(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=None)
        assert await self._repo(col).find_by_hash("nope", "email_verify") is None

    @pytest.mark.asyncio
    async def test_mark_as_used_sets_used_at(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        result = await self._repo(col).mark_as_used(TOKEN_OID)
        assert col.update_one.await_count == 1
        call_args = col.update_one.call_args[0]
        assert call_args[0] == {"_id": TOKEN_OID}
        assert "$set" in call_args[1]
        assert isinstance(call_args[1]["$set"]["used_at"], datetime)
        assert result is True

    @pytest.mark.asyncio
    async def test_mark_as_used_returns_false_on_miss(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock(modified_count=0))
        assert await self._repo(col).mark_as_used(TOKEN_OID) is False

    @pytest.mark.asyncio
    async def test_delete_by_user_no_type_filter(self):
        col = make_collection()
        col.delete_many = AsyncMock(return_value=MagicMock(deleted_count=2))
        count = await self._repo(col).delete_by_user(USER_OID)
        col.delete_many.assert_awaited_once_with({"user_id": USER_OID})
        assert count == 2

    @pytest.mark.asyncio
    async def test_delete_by_user_with_type_filter(self):
        col = make_collection()
        col.delete_many = AsyncMock(return_value=MagicMock(deleted_count=1))
        count = await self._repo(col).delete_by_user(USER_OID, "email_verify")
        col.delete_many.assert_awaited_once_with(
            {"user_id": USER_OID, "token_type": "email_verify"}
        )
        assert count == 1

    @pytest.mark.asyncio
    async def test_count_recent_builds_correct_query(self):
        col = make_collection()
        col.count_documents = AsyncMock(return_value=2)
        count = await self._repo(col).count_recent(USER_OID, "email_verify", minutes=30)
        assert col.count_documents.await_count == 1
        query = col.count_documents.call_args[0][0]
        assert query["user_id"] == USER_OID
        assert query["token_type"] == "email_verify"
        assert "$gte" in query["created_at"]
        assert count == 2


# ─────────────────────────────────────────────────────────────────────────────
# BlockedUrlRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestBlockedUrlRepository:
    def _repo(self, col=None):
        from repositories.blocked_url_repository import BlockedUrlRepository

        return BlockedUrlRepository(col or make_collection())

    @pytest.mark.asyncio
    async def test_get_patterns_returns_ids(self):
        col = make_collection()
        cursor = col.find.return_value
        cursor.to_list = AsyncMock(
            return_value=[{"_id": "pattern1"}, {"_id": "pattern2"}]
        )
        patterns = await self._repo(col).get_patterns()
        col.find.assert_called_once_with({}, {"_id": 1})
        assert patterns == ["pattern1", "pattern2"]

    @pytest.mark.asyncio
    async def test_get_patterns_returns_empty_list(self):
        col = make_collection()
        cursor = col.find.return_value
        cursor.to_list = AsyncMock(return_value=[])
        assert await self._repo(col).get_patterns() == []

    @pytest.mark.asyncio
    async def test_get_patterns_raises_on_db_error(self):
        col = make_collection()
        cursor = col.find.return_value
        cursor.to_list = AsyncMock(side_effect=Exception("db down"))
        with pytest.raises(Exception, match="db down"):
            await self._repo(col).get_patterns()


# ─────────────────────────────────────────────────────────────────────────────
# LegacyUrlRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestLegacyUrlRepository:
    def _repo(self, col=None):
        from repositories.legacy.legacy_url_repository import LegacyUrlRepository

        return LegacyUrlRepository(col or make_collection())

    @pytest.mark.asyncio
    async def test_find_by_id_returns_model(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=_legacy_url_doc())
        result = await self._repo(col).find_by_id("abc123")
        col.find_one.assert_awaited_once_with({"_id": "abc123"})
        assert result is not None
        assert result.url == "https://example.com"

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=None)
        assert await self._repo(col).find_by_id("missing") is None

    @pytest.mark.asyncio
    async def test_insert_prepends_id(self):
        col = make_collection()
        col.insert_one = AsyncMock(return_value=MagicMock())
        url_data = {"url": "https://example.com", "total-clicks": 0}
        await self._repo(col).insert("abc123", url_data)
        col.insert_one.assert_awaited_once_with({"_id": "abc123", **url_data})

    @pytest.mark.asyncio
    async def test_update_passes_update_doc_unchanged(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock())
        # Exact v1 click tracking update document — must be passed through unmodified
        update_ops = {
            "$inc": {
                "total-clicks": 1,
                "counter.2024-01-15": 1,
                "country.US.counts": 1,
                "browser.Chrome.counts": 1,
                "os_name.Linux.counts": 1,
                "referrer.example.com.counts": 1,
            },
            "$set": {
                "last-click": "15 Jan 2024 12:00:00",
                "last-click-browser": "Chrome",
                "last-click-os": "Linux",
                "last-click-country": "US",
                "average_redirection_time": 0.05,
            },
            "$addToSet": {
                "ips": "1.2.3.4",
                "country.US.ips": "1.2.3.4",
                "browser.Chrome.ips": "1.2.3.4",
                "os_name.Linux.ips": "1.2.3.4",
                "referrer.example.com.ips": "1.2.3.4",
            },
        }
        await self._repo(col).update("abc123", update_ops)
        col.update_one.assert_awaited_once_with({"_id": "abc123"}, update_ops)

    @pytest.mark.asyncio
    async def test_check_exists_true(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value={"_id": "abc123"})
        assert await self._repo(col).check_exists("abc123") is True
        col.find_one.assert_awaited_once_with({"_id": "abc123"}, {"_id": 1})

    @pytest.mark.asyncio
    async def test_check_exists_false(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=None)
        assert await self._repo(col).check_exists("missing") is False

    @pytest.mark.asyncio
    async def test_aggregate_returns_first_result(self):
        col = make_collection()
        cursor = col.aggregate.return_value
        cursor.to_list = AsyncMock(return_value=[{"result": "data"}])
        pipeline = [{"$match": {"_id": "abc123"}}]
        result = await self._repo(col).aggregate(pipeline)
        col.aggregate.assert_called_once_with(pipeline)
        assert result == {"result": "data"}

    @pytest.mark.asyncio
    async def test_aggregate_returns_none_on_empty(self):
        col = make_collection()
        cursor = col.aggregate.return_value
        cursor.to_list = AsyncMock(return_value=[])
        assert await self._repo(col).aggregate([]) is None


# ─────────────────────────────────────────────────────────────────────────────
# EmojiUrlRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestEmojiUrlRepository:
    def _repo(self, col=None):
        from repositories.legacy.emoji_url_repository import EmojiUrlRepository

        return EmojiUrlRepository(col or make_collection())

    def _emoji_doc(self):
        return {**_legacy_url_doc(), "_id": "🔥💯"}

    @pytest.mark.asyncio
    async def test_find_by_id_returns_model(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=self._emoji_doc())
        result = await self._repo(col).find_by_id("🔥💯")
        col.find_one.assert_awaited_once_with({"_id": "🔥💯"})
        assert result is not None

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=None)
        assert await self._repo(col).find_by_id("🔥💯") is None

    @pytest.mark.asyncio
    async def test_insert_prepends_id(self):
        col = make_collection()
        col.insert_one = AsyncMock(return_value=MagicMock())
        data = {"url": "https://example.com"}
        await self._repo(col).insert("🔥💯", data)
        col.insert_one.assert_awaited_once_with({"_id": "🔥💯", **data})

    @pytest.mark.asyncio
    async def test_update_passes_doc_unchanged(self):
        col = make_collection()
        col.update_one = AsyncMock(return_value=MagicMock())
        ops = {"$inc": {"total-clicks": 1}, "$set": {"last-click": "2024-01-01"}}
        await self._repo(col).update("🔥💯", ops)
        col.update_one.assert_awaited_once_with({"_id": "🔥💯"}, ops)

    @pytest.mark.asyncio
    async def test_check_exists_true(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value={"_id": "🔥💯"})
        assert await self._repo(col).check_exists("🔥💯") is True

    @pytest.mark.asyncio
    async def test_check_exists_false(self):
        col = make_collection()
        col.find_one = AsyncMock(return_value=None)
        assert await self._repo(col).check_exists("❌") is False

    @pytest.mark.asyncio
    async def test_aggregate_returns_first_result(self):
        col = make_collection()
        cursor = col.aggregate.return_value
        cursor.to_list = AsyncMock(return_value=[{"total": 5}])
        result = await self._repo(col).aggregate(
            [{"$group": {"_id": None, "total": {"$sum": 1}}}]
        )
        assert result == {"total": 5}

    @pytest.mark.asyncio
    async def test_aggregate_returns_none_on_empty(self):
        col = make_collection()
        cursor = col.aggregate.return_value
        cursor.to_list = AsyncMock(return_value=[])
        assert await self._repo(col).aggregate([]) is None


# ─────────────────────────────────────────────────────────────────────────────
# ensure_indexes
# ─────────────────────────────────────────────────────────────────────────────


class TestEnsureIndexes:
    @pytest.mark.asyncio
    async def test_ensure_indexes_calls_create_index(self):
        from repositories.indexes import ensure_indexes

        # Build a mock db with mock collections
        db = MagicMock()
        users_col = AsyncMock()
        urls_v2_col = AsyncMock()
        clicks_col = AsyncMock()
        api_keys_col = AsyncMock()
        tokens_col = AsyncMock()

        db.__getitem__ = lambda self, name: {
            "users": users_col,
            "urlsV2": urls_v2_col,
            "clicks": clicks_col,
            "api-keys": api_keys_col,
            "verification-tokens": tokens_col,
        }[name]

        # create_collection may raise (already exists) — that's fine
        db.create_collection = AsyncMock(side_effect=Exception("already exists"))

        await ensure_indexes(db)

        # Check a few critical indexes
        users_col.create_index.assert_any_await([("email", 1)], unique=True)
        urls_v2_col.create_index.assert_any_await([("alias", 1)], unique=True)
        urls_v2_col.create_index.assert_any_await([("owner_id", 1)])
        clicks_col.create_index.assert_any_await(
            [("meta.url_id", 1), ("clicked_at", -1)]
        )
        clicks_col.create_index.assert_any_await(
            [("meta.owner_id", 1), ("clicked_at", -1)]
        )
        api_keys_col.create_index.assert_any_await([("token_hash", 1)], unique=True)
        tokens_col.create_index.assert_any_await(
            [("expires_at", 1)], expireAfterSeconds=0
        )

    @pytest.mark.asyncio
    async def test_ensure_indexes_creates_timeseries_collection(self):
        from repositories.indexes import ensure_indexes

        db = MagicMock()
        for_col = AsyncMock()
        db.__getitem__ = lambda self, name: for_col
        db.create_collection = AsyncMock(return_value=None)

        await ensure_indexes(db)

        db.create_collection.assert_awaited_once_with(
            "clicks",
            timeseries={
                "timeField": "clicked_at",
                "metaField": "meta",
                "granularity": "seconds",
            },
        )
