"""
POST /api/v1/shorten — create a shortened URL.

Returns 201 on success with the URL details.
Auth is optional; API key users require `shorten:create` or `admin:all` scope.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request

from dependencies import (
    CurrentUser,
    check_api_key_scope,
    get_current_user,
    get_url_service,
)
from middleware.rate_limiter import dynamic_limit, limiter
from schemas.dto.requests.url import CreateUrlRequest
from schemas.dto.responses.url import UrlResponse
from services.url_service import UrlService
from shared.datetime_utils import to_unix_timestamp
from shared.ip_utils import get_client_ip

router = APIRouter()

_shorten_limit, _shorten_key = dynamic_limit(
    "60 per minute; 5000 per day",
    "20 per minute; 1000 per day",
)


@router.post("/shorten", status_code=201)
@limiter.limit(_shorten_limit, key_func=_shorten_key)
async def shorten_v1(
    request: Request,
    body: CreateUrlRequest,
    user: Optional[CurrentUser] = Depends(get_current_user),
    url_service: UrlService = Depends(get_url_service),
) -> UrlResponse:
    """Create a new shortened URL.

    Scope (if API key): ``shorten:create`` or ``admin:all``.
    Returns 201 on success.
    """
    check_api_key_scope(user, {"shorten:create", "admin:all"})

    owner_id = user.user_id if user is not None else None
    client_ip = get_client_ip(request)

    doc = await url_service.create(body, owner_id, client_ip)

    settings = request.app.state.settings
    return UrlResponse(
        alias=doc.alias,
        short_url=f"{settings.app_url.rstrip('/')}/{doc.alias}",
        long_url=doc.long_url,
        owner_id=str(doc.owner_id) if doc.owner_id else None,
        created_at=to_unix_timestamp(doc.created_at, default=0),
        status=doc.status,
        private_stats=doc.private_stats,
    )
