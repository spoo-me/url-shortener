"""
PATCH /api/v1/urls/{url_id}        — update URL properties
PATCH /api/v1/urls/{url_id}/status — update URL status only
DELETE /api/v1/urls/{url_id}       — delete a URL (returns 200)

All endpoints require authentication.  API key users require
``urls:manage`` or ``admin:all`` scope.
"""

from __future__ import annotations

from bson import ObjectId
from fastapi import APIRouter, Depends, Request

from dependencies import (
    CurrentUser,
    check_api_key_scope,
    get_url_service,
    require_auth,
)
from errors import ValidationError
from middleware.openapi import AUTH_RESPONSES, ERROR_RESPONSES
from middleware.rate_limiter import limiter
from shared.datetime_utils import to_unix_timestamp
from schemas.dto.requests.url import UpdateUrlRequest
from schemas.dto.responses.url import DeleteUrlResponse, UpdateUrlResponse
from services.url_service import UrlService

router = APIRouter(tags=["Link Management"])

_MANAGEMENT_SCOPES = {"urls:manage", "admin:all"}


def _parse_url_id(url_id: str) -> ObjectId:
    """Parse url_id path param to ObjectId, raise 400 on invalid format."""
    try:
        return ObjectId(url_id)
    except Exception:
        raise ValidationError("Invalid URL ID format")


@router.patch(
    "/urls/{url_id}",
    responses=AUTH_RESPONSES,
    operation_id="updateUrl",
    summary="Update URL",
)
@limiter.limit("120 per minute; 2000 per day")
async def update_url_v1(
    request: Request,
    url_id: str,
    body: UpdateUrlRequest,
    user: CurrentUser = Depends(require_auth),
    url_service: UrlService = Depends(get_url_service),
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
    check_api_key_scope(user, _MANAGEMENT_SCOPES)
    oid = _parse_url_id(url_id)
    doc = await url_service.update(oid, body, user.user_id)
    return UpdateUrlResponse(
        id=str(doc.id),
        alias=doc.alias,
        long_url=doc.long_url,
        status=doc.status,
        password_set=doc.password is not None,
        max_clicks=doc.max_clicks,
        expire_after=to_unix_timestamp(doc.expire_after),
        block_bots=doc.block_bots,
        private_stats=doc.private_stats,
        updated_at=to_unix_timestamp(doc.updated_at, default=0),
    )


@router.patch(
    "/urls/{url_id}/status",
    responses=ERROR_RESPONSES,
    operation_id="updateUrlStatus",
    summary="Update URL Status",
)
@limiter.limit("120 per minute; 2000 per day")
async def update_url_status_v1(
    request: Request,
    url_id: str,
    body: UpdateUrlRequest,
    user: CurrentUser = Depends(require_auth),
    url_service: UrlService = Depends(get_url_service),
) -> UpdateUrlResponse:
    """Update only the status of a URL (ACTIVE / INACTIVE).

    Convenience endpoint that accepts the same body as the full update but only
    applies the `status` field. All other fields in the request body are ignored.

    **Authentication**: Required — you must own the URL.

    **API Key Scope**: `urls:manage` or `admin:all`

    **Rate Limits**: 120/min, 2,000/day

    **Use Cases**:
    - Set `INACTIVE` to temporarily disable redirects without deleting the URL
    - Set `ACTIVE` to re-enable a previously disabled URL
    """
    check_api_key_scope(user, _MANAGEMENT_SCOPES)
    oid = _parse_url_id(url_id)

    # Pre-filter: only the status field is considered
    status_only = UpdateUrlRequest(status=body.status)

    doc = await url_service.update(oid, status_only, user.user_id)
    return UpdateUrlResponse(
        id=str(doc.id),
        alias=doc.alias,
        long_url=doc.long_url,
        status=doc.status,
        password_set=doc.password is not None,
        max_clicks=doc.max_clicks,
        expire_after=to_unix_timestamp(doc.expire_after),
        block_bots=doc.block_bots,
        private_stats=doc.private_stats,
        updated_at=to_unix_timestamp(doc.updated_at, default=0),
    )


@router.delete(
    "/urls/{url_id}",
    responses=ERROR_RESPONSES,
    operation_id="deleteUrl",
    summary="Delete URL",
)
@limiter.limit("60 per minute; 1000 per day")
async def delete_url_v1(
    request: Request,
    url_id: str,
    user: CurrentUser = Depends(require_auth),
    url_service: UrlService = Depends(get_url_service),
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
    check_api_key_scope(user, _MANAGEMENT_SCOPES)
    oid = _parse_url_id(url_id)
    await url_service.delete(oid, user.user_id)
    return DeleteUrlResponse(message="URL deleted", id=url_id)
