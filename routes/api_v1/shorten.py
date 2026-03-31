"""
POST /api/v1/shorten — create a shortened URL.

Returns 201 on success with the URL details.
Auth is optional; API key users require `shorten:create` or `admin:all` scope.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from dependencies import (
    SHORTEN_SCOPES,
    CurrentUser,
    get_url_service,
    optional_scopes_verified,
)
from middleware.openapi import AUTH_RESPONSES, OPTIONAL_AUTH_SECURITY
from middleware.rate_limiter import Limits, dynamic_limit, limiter
from schemas.dto.requests.url import CreateUrlRequest
from schemas.dto.responses.url import UrlResponse
from services.url_service import UrlService
from shared.datetime_utils import to_unix_timestamp
from shared.ip_utils import get_client_ip

router = APIRouter(tags=["URL Shortening"])

_shorten_limit, _shorten_key = dynamic_limit(Limits.API_AUTHED, Limits.API_ANON)


@router.post(
    "/shorten",
    status_code=201,
    responses=AUTH_RESPONSES,
    openapi_extra=OPTIONAL_AUTH_SECURITY,
    operation_id="shortenUrl",
    summary="Create Shortened URL",
)
@limiter.limit(_shorten_limit, key_func=_shorten_key)
async def shorten_v1(
    request: Request,
    body: CreateUrlRequest,
    user: CurrentUser | None = Depends(optional_scopes_verified(SHORTEN_SCOPES)),  # noqa: B008
    url_service: UrlService = Depends(get_url_service),
) -> UrlResponse:
    """Create a new shortened URL.

    Create a shortened URL with optional customization including password protection,
    expiration, click limits, and bot blocking.

    **Authentication**: Optional — higher rate limits when authenticated.

    **API Key Scope**: `shorten:create` or `admin:all`

    **Rate Limits**:

    - Authenticated: 60/min, 5,000/day
    - Anonymous: 20/min, 1,000/day

    **Anonymous Usage Consequences**:

    - Lower rate limits
    - Cannot manage or view URLs later
    - Cannot use private stats
    - URLs not linked to any account
    """
    owner_id = user.user_id if user is not None else None
    client_ip = get_client_ip(request)

    doc, raw_token = await url_service.create(body, owner_id, client_ip)

    settings = request.app.state.settings
    return UrlResponse(
        alias=doc.alias,
        short_url=f"{settings.app_url.rstrip('/')}/{doc.alias}",
        long_url=doc.long_url,
        owner_id=str(doc.owner_id) if doc.owner_id else None,
        created_at=to_unix_timestamp(doc.created_at, default=0),
        status=doc.status,
        private_stats=doc.private_stats,
        manage_token=raw_token,
    )
