"""Unit tests for ClickRepository."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from .conftest import make_collection, URL_OID, USER_OID


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
