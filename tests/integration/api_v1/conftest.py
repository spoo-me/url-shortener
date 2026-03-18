"""
Shared helpers for /api/v1/* integration tests.

All DB / Redis / external-service calls are eliminated via
dependency_overrides and a mock lifespan — no real infrastructure needed.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock

from bson import ObjectId
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/")

from config import AppSettings
from dependencies import CurrentUser
from middleware.error_handler import register_error_handlers
from middleware.rate_limiter import limiter
from routes.api_v1 import router as api_v1_router
from schemas.models.api_key import ApiKeyDoc
from schemas.models.url import UrlV2Doc


def _build_test_app(overrides: dict) -> FastAPI:
    """Build a minimal FastAPI app with mock lifespan and given dependency overrides."""
    settings = AppSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.db = MagicMock()
        app.state.redis = None
        yield

    application = FastAPI(lifespan=lifespan)
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_error_handlers(application)
    application.include_router(api_v1_router)

    for dep, override in overrides.items():
        application.dependency_overrides[dep] = override

    return application


def _make_url_doc(
    alias: str = "testme", owner_id: Optional[ObjectId] = None
) -> UrlV2Doc:
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
    user_id: Optional[ObjectId] = None,
    email_verified: bool = True,
    api_key_doc: Optional[ApiKeyDoc] = None,
) -> CurrentUser:
    return CurrentUser(
        user_id=user_id or ObjectId(),
        email_verified=email_verified,
        api_key_doc=api_key_doc,
    )


def _make_api_key_doc(
    user_id: Optional[ObjectId] = None, scopes: Optional[list] = None
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
