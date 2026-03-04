"""
GET /api/v1/urls — list authenticated user's shortened URLs.

Requires authentication. Returns paginated list with camelCase keys.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from dependencies import (
    CurrentUser,
    check_api_key_scope,
    get_url_service,
    require_auth,
)
from middleware.rate_limiter import limiter
from schemas.dto.requests.url import ListUrlsQuery
from services.url_service import UrlService

router = APIRouter()


@router.get("/urls")
@limiter.limit("60 per minute; 5000 per day")
async def list_urls_v1(
    request: Request,
    query: ListUrlsQuery = Depends(),
    user: CurrentUser = Depends(require_auth),
    url_service: UrlService = Depends(get_url_service),
) -> dict:
    """List all URLs owned by the authenticated user.

    Scope (if API key): ``urls:manage``, ``urls:read``, or ``admin:all``.
    Returns paginated response with ``hasNext`` (camelCase).
    """
    check_api_key_scope(user, {"urls:manage", "urls:read", "admin:all"})
    return await url_service.list_by_owner(user.user_id, query)
