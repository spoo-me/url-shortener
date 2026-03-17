"""
GET /api/v1/urls — list authenticated user's shortened URLs.

Requires authentication. Returns paginated list with camelCase keys.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from dependencies import (
    CurrentUser,
    check_api_key_scope,
    get_url_service,
    require_auth,
)
from middleware.openapi import ERROR_RESPONSES
from middleware.rate_limiter import limiter
from schemas.dto.requests.url import ListUrlsQuery
from schemas.dto.responses.url import UrlListResponse
from services.url_service import UrlService

router = APIRouter(tags=["Link Management"])


@router.get(
    "/urls",
    responses=ERROR_RESPONSES,
    operation_id="listUrls",
    summary="List Your URLs",
)
@limiter.limit("60 per minute; 5000 per day")
async def list_urls_v1(
    request: Request,
    query: Annotated[ListUrlsQuery, Query()],
    user: CurrentUser = Depends(require_auth),
    url_service: UrlService = Depends(get_url_service),
) -> UrlListResponse:
    """List all URLs owned by the authenticated user.

    Returns a paginated list of shortened URLs with support for filtering,
    sorting, and full-text search on aliases and destination URLs.

    **Authentication**: Required.

    **API Key Scope**: `urls:manage`, `urls:read`, or `admin:all`

    **Rate Limits**: 60/min, 5,000/day

    **Pagination**: Use `page` and `pageSize` query params. Response includes
    `hasNext` boolean and `total` count.

    **Sorting**: Sort by `created_at`, `last_click`, or `total_clicks` in
    ascending or descending order.

    **Filtering**: Pass a JSON-encoded `filter` parameter with fields like
    `status`, `createdAfter`, `createdBefore`, `passwordSet`, `maxClicksSet`,
    and `search`.
    """
    check_api_key_scope(user, {"urls:manage", "urls:read", "admin:all"})
    return await url_service.list_by_owner(user.user_id, query)
