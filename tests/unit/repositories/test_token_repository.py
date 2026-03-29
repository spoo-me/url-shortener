"""Unit tests for TokenRepository."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from .conftest import TOKEN_OID, USER_OID, _token_doc, make_collection


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
