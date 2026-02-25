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

from config import AppSettings
from errors import register_error_handlers
from routes.health_routes import router as health_router


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

        # ensure_indexes is wired in Phase 6 when the repository layer exists.
        # Guarded with hasattr so Phase 1 boots cleanly without it.
        if hasattr(app.state, "ensure_indexes"):
            await app.state.ensure_indexes(app.state.db)

        yield

        # ── Shutdown ─────────────────────────────────────────────────────────
        mongo_client.close()
        if redis_client is not None:
            await redis_client.aclose()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url=settings.docs_url,
        redoc_url=None,
        lifespan=lifespan,
    )

    # all origins allowed with credentials support.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(health_router)

    return app
