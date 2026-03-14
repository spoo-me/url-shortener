"""Shared helpers for repository unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from bson import ObjectId


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

    In PyMongo async (4.16+):
    - find() is *synchronous* — returns a cursor directly (MagicMock)
    - aggregate() is *async* — returns a coroutine that resolves to a cursor (AsyncMock)
    - find_one(), count_documents(), etc. are async (handled by AsyncMock default)
    """
    col = AsyncMock()
    cursor = make_cursor()
    col.find = MagicMock(return_value=cursor)
    col.aggregate = AsyncMock(return_value=cursor)
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
