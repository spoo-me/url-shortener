"""Unit tests for ensure_indexes."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


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
