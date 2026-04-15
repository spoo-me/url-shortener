"""
GET /api/v1/urls — list authenticated user's shortened URLs.

Requires authentication. Returns paginated list with camelCase keys.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from dependencies import (
    URL_READ_SCOPES,
    CurrentUser,
    UrlSvc,
    require_scopes,
)
from middleware.openapi import ERROR_RESPONSES
from middleware.rate_limiter import Limits, limiter
from schemas.dto.requests.url import ListUrlsQuery
from schemas.dto.responses.url import UrlListItem, UrlListResponse

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
    url_service: UrlSvc,
    user: CurrentUser = Depends(require_scopes(URL_READ_SCOPES)),  # noqa: B008
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
    result = await url_service.list_by_owner(user.user_id, query)
    result["items"] = [UrlListItem.from_doc(doc) for doc in result["items"]]
    return result
