"""
PATCH /api/v1/urls/{url_id}        — update URL properties
PATCH /api/v1/urls/{url_id}/status — update URL status only
DELETE /api/v1/urls/{url_id}       — delete a URL (returns 200)

All endpoints require authentication.  API key users require
``urls:manage`` or ``admin:all`` scope.
"""

from __future__ import annotations

from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, Path, Request

from dependencies import (
    URL_MANAGEMENT_SCOPES,
    CurrentUser,
    UrlSvc,
    require_scopes,
)
from errors import ValidationError
from middleware.openapi import AUTH_RESPONSES, ERROR_RESPONSES
from middleware.rate_limiter import Limits, limiter
from schemas.dto.requests.url import UpdateUrlRequest, UpdateUrlStatusRequest
from schemas.dto.responses.url import DeleteUrlResponse, UpdateUrlResponse

router = APIRouter(tags=["Link Management"])


def _parse_url_id(url_id: str) -> ObjectId:
    """Parse url_id path param to ObjectId, raise 400 on invalid format."""
    try:
        return ObjectId(url_id)
    except Exception:
        raise ValidationError("Invalid URL ID format") from None


@router.patch(
    "/urls/{url_id}",
    responses=AUTH_RESPONSES,
    operation_id="updateUrl",
    summary="Update URL",
)
@limiter.limit(Limits.URL_MANAGE)
async def update_url_v1(
    request: Request,
    url_id: Annotated[
        str,
        Path(
            description="Unique identifier of the URL",
            min_length=24,
            max_length=24,
            pattern=r"^[0-9a-f]{24}$",
        ),
    ],
    body: UpdateUrlRequest,
    url_service: UrlSvc,
    user: CurrentUser = Depends(require_scopes(URL_MANAGEMENT_SCOPES)),  # noqa: B008
) -> UpdateUrlResponse:
    """Update an existing URL's properties.

    Partially update a shortened URL. Only provided fields are modified; omitted
    fields remain unchanged. Pass `null` to remove optional settings like
    `password`, `max_clicks`, or `expire_after`.

    **Authentication**: Required — you must own the URL.

    **API Key Scope**: `urls:manage` or `admin:all`

    **Rate Limits**: 120/min, 2,000/day

    **Updatable Fields**: `long_url`, `alias`, `password`, `block_bots`,
    `max_clicks`, `expire_after`, `private_stats`, `status`

    **Notes**:

    - Setting `max_clicks` to `0` or `null` removes the click limit
    - Changing the `alias` checks availability and may fail with 409 Conflict
    - The `url_id` is the MongoDB ObjectId, not the alias
    """
    oid = _parse_url_id(url_id)
    doc = await url_service.update(oid, body, user.user_id)
    return UpdateUrlResponse.from_doc(doc)


@router.patch(
    "/urls/{url_id}/status",
    responses=ERROR_RESPONSES,
    operation_id="updateUrlStatus",
    summary="Update URL Status",
)
@limiter.limit(Limits.URL_MANAGE)
async def update_url_status_v1(
    request: Request,
    url_id: Annotated[
        str,
        Path(
            description="Unique identifier of the URL",
            min_length=24,
            max_length=24,
            pattern=r"^[0-9a-f]{24}$",
        ),
    ],
    body: UpdateUrlStatusRequest,
    url_service: UrlSvc,
    user: CurrentUser = Depends(require_scopes(URL_MANAGEMENT_SCOPES)),  # noqa: B008
) -> UpdateUrlResponse:
    """Update only the status of a URL (ACTIVE / INACTIVE).

    Toggle a URL between active and inactive without modifying other properties.

    **Authentication**: Required — you must own the URL.

    **API Key Scope**: `urls:manage` or `admin:all`

    **Rate Limits**: 120/min, 2,000/day

    **Status Values** (user-editable via this endpoint):

    - `ACTIVE` — URL is accessible and redirects normally
    - `INACTIVE` — URL is disabled and returns an error page

    **Note**: `BLOCKED` is an admin-set status — blocked URLs cannot be modified
    or deleted by the owner. `EXPIRED` URLs (auto-set on max clicks or expiry
    time) can be reactivated by setting status back to `ACTIVE`.

    **Use Cases**:

    - Set `INACTIVE` to temporarily disable redirects without deleting the URL
    - Set `ACTIVE` to re-enable a previously disabled URL
    """
    oid = _parse_url_id(url_id)

    status_only = UpdateUrlRequest(status=body.status)

    doc = await url_service.update(oid, status_only, user.user_id)
    return UpdateUrlResponse.from_doc(doc)


@router.delete(
    "/urls/{url_id}",
    responses=ERROR_RESPONSES,
    operation_id="deleteUrl",
    summary="Delete URL",
)
@limiter.limit(Limits.URL_DELETE)
async def delete_url_v1(
    request: Request,
    url_id: Annotated[
        str,
        Path(
            description="Unique identifier of the URL",
            min_length=24,
            max_length=24,
            pattern=r"^[0-9a-f]{24}$",
        ),
    ],
    url_service: UrlSvc,
    user: CurrentUser = Depends(require_scopes(URL_MANAGEMENT_SCOPES)),  # noqa: B008
) -> DeleteUrlResponse:
    """Delete a URL permanently.

    **This action is IRREVERSIBLE.** The URL, its alias, and all associated
    click analytics data will be permanently deleted. The alias may be reclaimed
    by another user afterward.

    **Authentication**: Required — you must own the URL.

    **API Key Scope**: `urls:manage` or `admin:all`

    **Rate Limits**: 60/min, 1,000/day

    **Recommendation**: Consider setting the URL status to `INACTIVE` via
    `PATCH /urls/{url_id}/status` instead if you may want to restore it later.
    """
    oid = _parse_url_id(url_id)
    await url_service.delete(oid, user.user_id)
    return DeleteUrlResponse(message="URL deleted", id=url_id)
