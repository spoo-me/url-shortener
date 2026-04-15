"""
App-level infrastructure dependency providers.

Thin wrappers that pull singletons off app.state — set up during lifespan
in app.py. These are the base-level deps that auth and service deps build on.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Request

from config import AppSettings, JWTSettings
from infrastructure.geoip import GeoIPService
from schemas.models.app import AppEntry


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


def get_jwt_config(request: Request) -> JWTSettings:
    """Return the JWT configuration from app settings."""
    return request.app.state.settings.jwt


def get_oauth_providers(request: Request) -> dict[str, Any]:
    """Return the OAuth provider registry from app.state."""
    return getattr(request.app.state, "oauth_providers", {})


def get_app_registry(request: Request) -> dict[str, AppEntry]:
    """Return the app registry from app.state."""
    return request.app.state.app_registry


# ── Annotated type aliases ───────────────────────────────────────────────────

Settings = Annotated[AppSettings, Depends(get_settings)]
JwtConfig = Annotated[JWTSettings, Depends(get_jwt_config)]
OAuthProviders = Annotated[dict[str, Any], Depends(get_oauth_providers)]
AppRegistryDep = Annotated[dict[str, AppEntry], Depends(get_app_registry)]
