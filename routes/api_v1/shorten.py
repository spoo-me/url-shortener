"""
POST /api/v1/shorten — create a shortened URL.

Returns 201 on success with the URL details.
Auth is optional; API key users require `shorten:create` or `admin:all` scope.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from dependencies import (
    SHORTEN_SCOPES,
    CurrentUser,
    Settings,
    UrlSvc,
    optional_scopes_verified,
)
from middleware.openapi import AUTH_RESPONSES, OPTIONAL_AUTH_SECURITY
from middleware.rate_limiter import Limits, dynamic_limit, limiter
from schemas.dto.requests.url import AliasCheckQuery, CreateUrlRequest
from schemas.dto.responses.url import AliasCheckResponse, UrlResponse
from shared.ip_utils import get_client_ip

router = APIRouter(tags=["URL Shortening"])

_shorten_limit, _shorten_key = dynamic_limit(Limits.API_AUTHED, Limits.API_ANON)
_check_limit, _check_key = dynamic_limit(Limits.API_CHECK_AUTHED, Limits.API_CHECK_ANON)


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
    url_service: UrlSvc,
    settings: Settings,
    user: CurrentUser | None = Depends(optional_scopes_verified(SHORTEN_SCOPES)),  # noqa: B008
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

    doc = await url_service.create(body, owner_id, client_ip)
    return UrlResponse.from_doc(doc, settings.app_url)


@router.get(
    "/shorten/check-alias",
    responses=AUTH_RESPONSES,
    openapi_extra=OPTIONAL_AUTH_SECURITY,
    operation_id="checkAliasAvailability",
    summary="Check Alias Availability",
)
@limiter.limit(_check_limit, key_func=_check_key)
async def check_alias(
    request: Request,
    url_service: UrlSvc,
    query: Annotated[AliasCheckQuery, Query()],
    _user: CurrentUser | None = Depends(optional_scopes_verified(SHORTEN_SCOPES)),  # noqa: B008
) -> AliasCheckResponse:
    """Check whether a proposed alias would be accepted by POST /api/v1/shorten.

    Reason codes on a negative result (``length``/``format``/``taken``) let the
    UI render precise inline feedback without duplicating the validation rules.

    **Authentication**: Optional — higher rate limits when authenticated.
    """
    result = await url_service.check_alias(query.alias)
    return AliasCheckResponse(
        available=result == "available",
        reason=None if result == "available" else result,
    )
