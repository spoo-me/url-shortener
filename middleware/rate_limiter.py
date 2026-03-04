"""
slowapi rate limiter — shared instance used across all routes.

Phase 14 adds the full middleware stack (request logging, security headers).
This module provides only the limiter singleton needed by routes.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def dynamic_limit(authenticated: str, anonymous: str) -> tuple:
    """Return a (limit_fn, key_fn) pair for two-tier authenticated/anonymous rate limiting.

    Usage in routes::

        _limit, _key = dynamic_limit("60 per minute", "20 per minute")

        @router.get("/endpoint")
        @limiter.limit(_limit, key_func=_key)
        async def endpoint(request: Request, ...): ...

    The key function encodes auth status + IP so that authenticated and
    anonymous users share separate buckets for the same endpoint.
    No token validation is performed — just presence check.
    """

    def _key(request: Request) -> str:
        """Produce a rate-limit key encoding auth status + client IP."""
        ip = get_remote_address(request)
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer ") or request.cookies.get("access_token"):
            return f"auth:{ip}"
        return f"anon:{ip}"

    def _limit(key: str) -> str:
        """Return the appropriate limit string based on auth tier in key."""
        return authenticated if key.startswith("auth:") else anonymous

    return _limit, _key
