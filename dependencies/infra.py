"""
App-level infrastructure dependency providers.

Thin wrappers that pull singletons off app.state — set up during lifespan
in app.py. These are the base-level deps that auth and service deps build on.
"""

from __future__ import annotations

from fastapi import Depends, Request

from config import AppSettings
from infrastructure.cache.url_cache import UrlCache
from infrastructure.geoip import GeoIPService


def get_settings(request: Request) -> AppSettings:
    """Return the AppSettings instance stored on app.state."""
    return request.app.state.settings


async def get_db(request: Request):
    """Return the async MongoDB database from app.state."""
    return request.app.state.db


async def get_redis(request: Request):
    """Return the async Redis client from app.state (may be None if not configured)."""
    return request.app.state.redis


def get_email_provider(request: Request):
    """Return the shared ZeptoMailProvider singleton from app.state."""
    return request.app.state.email_provider


def get_geoip_service(request: Request) -> GeoIPService:
    """Return the GeoIPService singleton from app.state."""
    return request.app.state.geoip


def get_url_cache(
    redis=Depends(get_redis),
    settings: AppSettings = Depends(get_settings),
) -> UrlCache:
    """Return a UrlCache wrapping the shared Redis client."""
    return UrlCache(redis, ttl_seconds=settings.redis.redis_ttl_seconds)
