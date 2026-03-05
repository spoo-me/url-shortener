"""
FastAPI application factory.
create_app() is the single entry point for building the app.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import redis.asyncio as aioredis
import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from starlette.middleware.sessions import SessionMiddleware

from config import AppSettings
from errors import register_error_handlers
from infrastructure.email.zeptomail import ZeptoMailProvider
from infrastructure.http_client import HttpClient
from infrastructure.oauth_clients import init_oauth
from middleware.rate_limiter import limiter
from repositories.indexes import ensure_indexes
from routes.api_v1 import router as api_v1_router
from routes.auth_routes import router as auth_router
from routes.health_routes import router as health_router
from routes.oauth_routes import router as oauth_router


def create_app(settings: Optional[AppSettings] = None) -> FastAPI:
    """Create and return a fully configured FastAPI application."""
    if settings is None:
        settings = AppSettings()

    # Initialise Sentry before anything else so it captures startup errors
    if settings.sentry.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry.sentry_dsn,
            send_default_pii=settings.sentry.sentry_send_pii,
            traces_sample_rate=settings.sentry.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry.sentry_profile_sample_rate,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # ── Startup ──────────────────────────────────────────────────────────
        mongo_client: AsyncMongoClient = AsyncMongoClient(settings.db.mongodb_uri)
        app.state.mongo_client = mongo_client
        app.state.db = mongo_client[settings.db.db_name]
        app.state.settings = settings

        # Redis is optional; self-hosters may not configure it
        redis_client = None
        if settings.redis.redis_uri:
            redis_client = aioredis.from_url(
                settings.redis.redis_uri,
                encoding="utf-8",
                decode_responses=True,
            )
        app.state.redis = redis_client

        # OAuth clients — stored on app.state for route-layer access
        _, oauth_providers = init_oauth(settings.oauth)
        app.state.oauth_providers = oauth_providers

        # Shared HTTP client + email provider — singletons to preserve connection pooling
        http_client = HttpClient(timeout=5.0)
        app.state.http_client = http_client
        app.state.email_provider = ZeptoMailProvider(
            settings.email, http_client, app_url=settings.app_url
        )

        await ensure_indexes(app.state.db)

        yield

        # ── Shutdown ─────────────────────────────────────────────────────────
        await mongo_client.close()
        if redis_client is not None:
            await redis_client.aclose()
        await http_client.aclose()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url=settings.docs_url,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Session middleware — required by Authlib Starlette OAuth client for state storage
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

    # all origins allowed with credentials support.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(oauth_router)
    app.include_router(api_v1_router)

    return app
