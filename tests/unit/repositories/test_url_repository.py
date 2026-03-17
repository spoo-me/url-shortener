"""Unit tests for UrlRepository."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from pymongo.errors import (
    DuplicateKeyError,
    OperationFailure,
    ServerSelectionTimeoutError,
)

from .conftest import make_collection, _url_v2_doc, URL_OID, USER_OID


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

    # ── Error path tests ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_find_by_alias_raises_on_operation_failure(self):
        """OperationFailure (e.g. query plan error) propagates from find_by_alias."""
        col = make_collection()
        col.find_one = AsyncMock(side_effect=OperationFailure("query failed"))
        with pytest.raises(OperationFailure):
            await self._repo(col).find_by_alias("abc")

    @pytest.mark.asyncio
    async def test_find_by_alias_raises_on_server_timeout(self):
        """ServerSelectionTimeoutError (e.g. MongoDB unreachable) propagates."""
        col = make_collection()
        col.find_one = AsyncMock(side_effect=ServerSelectionTimeoutError("timed out"))
        with pytest.raises(ServerSelectionTimeoutError):
            await self._repo(col).find_by_alias("abc")

    @pytest.mark.asyncio
    async def test_insert_raises_duplicate_key(self):
        """DuplicateKeyError on insert propagates (alias unique index violation)."""
        col = make_collection()
        col.insert_one = AsyncMock(
            side_effect=DuplicateKeyError("E11000 duplicate key")
        )
        with pytest.raises(DuplicateKeyError):
            await self._repo(col).insert({"alias": "abc1234"})

    @pytest.mark.asyncio
    async def test_insert_raises_on_operation_failure(self):
        """OperationFailure on insert propagates."""
        col = make_collection()
        col.insert_one = AsyncMock(side_effect=OperationFailure("write failed"))
        with pytest.raises(OperationFailure):
            await self._repo(col).insert({"alias": "abc1234"})

    @pytest.mark.asyncio
    async def test_update_raises_on_server_timeout(self):
        """ServerSelectionTimeoutError during update propagates."""
        col = make_collection()
        col.update_one = AsyncMock(side_effect=ServerSelectionTimeoutError("timed out"))
        with pytest.raises(ServerSelectionTimeoutError):
            await self._repo(col).update(URL_OID, {"$set": {"status": "INACTIVE"}})

    @pytest.mark.asyncio
    async def test_non_pymongo_error_propagates_uncaught(self):
        """Errors outside pymongo (e.g. ValueError) are NOT caught by the repo."""
        col = make_collection()
        col.find_one = AsyncMock(side_effect=ValueError("unexpected"))
        with pytest.raises(ValueError, match="unexpected"):
            await self._repo(col).find_by_alias("abc")
