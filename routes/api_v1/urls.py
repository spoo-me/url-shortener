"""
GET /api/v1/urls — list authenticated user's shortened URLs.

Requires authentication. Returns paginated list with camelCase keys.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from dependencies import (
    CurrentUser,
    URL_READ_SCOPES,
    get_url_service,
    require_scopes,
)
from middleware.openapi import ERROR_RESPONSES
from middleware.rate_limiter import Limits, limiter
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
@limiter.limit(Limits.API_AUTHED)
async def list_urls_v1(
    request: Request,
    query: Annotated[ListUrlsQuery, Query()],
    user: CurrentUser = Depends(require_scopes(URL_READ_SCOPES)),
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
    return await url_service.list_by_owner(user.user_id, query)
