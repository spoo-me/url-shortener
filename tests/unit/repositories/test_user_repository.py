"""Unit tests for UserRepository."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from pymongo.errors import (
    DuplicateKeyError,
    OperationFailure,
    ServerSelectionTimeoutError,
)

from .conftest import make_collection, USER_OID


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

    # ── Error path tests ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_find_by_email_raises_on_operation_failure(self):
        """OperationFailure propagates from find_by_email."""
        col = make_collection()
        col.find_one = AsyncMock(side_effect=OperationFailure("query failed"))
        with pytest.raises(OperationFailure):
            await self._repo(col).find_by_email("test@example.com")

    @pytest.mark.asyncio
    async def test_find_by_id_raises_on_server_timeout(self):
        """ServerSelectionTimeoutError (MongoDB unreachable) propagates from find_by_id."""
        col = make_collection()
        col.find_one = AsyncMock(side_effect=ServerSelectionTimeoutError("timed out"))
        with pytest.raises(ServerSelectionTimeoutError):
            await self._repo(col).find_by_id(USER_OID)

    @pytest.mark.asyncio
    async def test_create_raises_duplicate_key(self):
        """DuplicateKeyError on create propagates (email unique index violation)."""
        col = make_collection()
        col.insert_one = AsyncMock(
            side_effect=DuplicateKeyError("E11000 duplicate key")
        )
        with pytest.raises(DuplicateKeyError):
            await self._repo(col).create({"email": "existing@example.com"})

    @pytest.mark.asyncio
    async def test_create_raises_on_operation_failure(self):
        """OperationFailure on create propagates."""
        col = make_collection()
        col.insert_one = AsyncMock(side_effect=OperationFailure("write failed"))
        with pytest.raises(OperationFailure):
            await self._repo(col).create({"email": "new@example.com"})

    @pytest.mark.asyncio
    async def test_update_raises_on_server_timeout(self):
        """ServerSelectionTimeoutError during update propagates."""
        col = make_collection()
        col.update_one = AsyncMock(side_effect=ServerSelectionTimeoutError("timed out"))
        with pytest.raises(ServerSelectionTimeoutError):
            await self._repo(col).update(USER_OID, {"$set": {"email_verified": True}})
