"""
FastAPI dependency providers.

All injectable dependencies are defined here as plain async functions
used with FastAPI's Depends() system.

Additional providers (repositories, services, auth) are added in later phases
as their targets are built.
"""

from __future__ import annotations

from fastapi import Request

from config import AppSettings


def get_settings(request: Request) -> AppSettings:
    """Return the AppSettings instance stored on app.state."""
    return request.app.state.settings


async def get_db(request: Request):
    """Return the async MongoDB database from app.state."""
    return request.app.state.db


async def get_redis(request: Request):
    """Return the async Redis client from app.state (may be None if not configured)."""
    return request.app.state.redis
