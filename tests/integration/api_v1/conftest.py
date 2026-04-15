"""
Shared helpers for /api/v1/* integration tests.

All DB / Redis / external-service calls are eliminated via
dependency_overrides and a mock lifespan — no real infrastructure needed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import FastAPI

from dependencies import CurrentUser
from routes.api_v1 import router as api_v1_router
from schemas.models.api_key import ApiKeyDoc
from schemas.models.url import UrlV2Doc
from tests.conftest import build_test_app


def _build_test_app(overrides: dict) -> FastAPI:
    """Thin wrapper around the shared builder for api_v1 tests."""
    return build_test_app(api_v1_router, overrides=overrides)


def _make_url_doc(alias: str = "testme", owner_id: ObjectId | None = None) -> UrlV2Doc:
    oid = owner_id or ObjectId()
    return UrlV2Doc(
        **{
            "_id": ObjectId(),
            "alias": alias,
            "owner_id": oid,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "long_url": "https://example.com/long",
            "status": "ACTIVE",
            "private_stats": False,
        }
    )


def _make_user(
    user_id: ObjectId | None = None,
    email_verified: bool = True,
    api_key_doc: ApiKeyDoc | None = None,
) -> CurrentUser:
    return CurrentUser(
        user_id=user_id or ObjectId(),
        email_verified=email_verified,
        api_key_doc=api_key_doc,
    )


def _make_api_key_doc(
    user_id: ObjectId | None = None, scopes: list | None = None
) -> ApiKeyDoc:
    return ApiKeyDoc(
        **{
            "_id": ObjectId(),
            "user_id": user_id or ObjectId(),
            "token_prefix": "AbCdEfGh",
            "token_hash": "testhash",
            "name": "Test Key",
            "scopes": scopes or ["shorten:create"],
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "revoked": False,
        }
    )
