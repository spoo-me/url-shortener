"""
Root test conftest — shared test app builder.

Provides ``build_test_app()`` for integration tests that need a minimal
FastAPI app with mock infrastructure and dependency overrides.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/")

from config import AppSettings
from middleware.error_handler import register_error_handlers
from middleware.rate_limiter import limiter

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static"
)


def build_test_app(
    *routers: APIRouter,
    overrides: dict | None = None,
    extra_state: dict[str, Any] | None = None,
    mount_static: bool = True,
) -> FastAPI:
    """Build a minimal FastAPI app with mock infrastructure for testing.

    Args:
        *routers:     Routers to include (e.g. ``auth_router``, ``api_v1_router``).
        overrides:    Dependency overrides dict (e.g. ``{get_credential_service: lambda: mock}``).
        extra_state:  Additional attributes to set on ``app.state`` beyond defaults.
        mount_static: Whether to mount the /static directory (default True).

    The default lifespan sets:
        - ``app.state.settings`` — real ``AppSettings()``
        - ``app.state.db`` — ``MagicMock()``
        - ``app.state.redis`` — ``None``
        - ``app.state.email_provider`` — ``MagicMock()``
        - ``app.state.http_client`` — ``MagicMock()``
        - ``app.state.oauth_providers`` — ``{}``
        - ``app.state.app_registry`` — ``{}``
        - ``app.state.credential_service`` — ``AsyncMock()``
        - ``app.state.verification_service`` — ``AsyncMock()``
        - ``app.state.password_service`` — ``AsyncMock()``
        - ``app.state.device_auth_service`` — ``AsyncMock()``
        - ``app.state.user_repo`` — ``AsyncMock()``
        - ``app.state.token_factory`` — ``AsyncMock()``

    Use ``extra_state`` to override or extend any of these defaults.
    """
    settings = AppSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.db = MagicMock()
        app.state.redis = None
        app.state.email_provider = MagicMock()
        app.state.http_client = MagicMock()
        app.state.oauth_providers = {}
        app.state.app_registry = {}
        # Service mocks (so dependency getters that read app.state don't fail)
        app.state.credential_service = AsyncMock()
        app.state.verification_service = AsyncMock()
        app.state.password_service = AsyncMock()
        app.state.device_auth_service = AsyncMock()
        app.state.user_repo = AsyncMock()
        app.state.token_factory = AsyncMock()
        app.state.url_service = AsyncMock()
        app.state.stats_service = AsyncMock()
        app.state.export_service = AsyncMock()
        app.state.api_key_service = AsyncMock()
        app.state.oauth_service = AsyncMock()
        app.state.profile_picture_service = AsyncMock()
        app.state.contact_service = AsyncMock()
        app.state.click_service = AsyncMock()
        app.state.app_grant_repo = AsyncMock()
        if extra_state:
            for key, value in extra_state.items():
                setattr(app.state, key, value)
        yield

    application = FastAPI(lifespan=lifespan)
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_error_handlers(application)

    if mount_static and os.path.isdir(_STATIC_DIR):
        application.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    for router in routers:
        application.include_router(router)

    if overrides:
        application.dependency_overrides.update(overrides)

    return application
