"""
POST   /api/v1/keys          — create an API key
GET    /api/v1/keys          — list API keys for the current user
DELETE /api/v1/keys/{key_id} — delete (?revoke=false) or revoke (?revoke=true) a key

All endpoints require JWT authentication (API keys may NOT be used to manage
other API keys — only JWT Bearer auth is accepted here, matching the original).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, Query, Request

from dependencies import (
    CurrentUser,
    get_api_key_service,
    require_auth,
    require_verified_email,
)
from errors import NotFoundError, ValidationError
from middleware.rate_limiter import limiter
from schemas.dto.requests.api_key import CreateApiKeyRequest
from schemas.dto.responses.api_key import (
    ApiKeyActionResponse,
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    ApiKeysListResponse,
)
from services.api_key_service import ApiKeyService
from shared.datetime_utils import parse_datetime, to_unix_timestamp

router = APIRouter()


@router.post("/keys", status_code=201)
@limiter.limit("5 per hour")
async def create_api_key(
    request: Request,
    body: CreateApiKeyRequest,
    user: CurrentUser = Depends(require_verified_email),
    api_key_service: ApiKeyService = Depends(get_api_key_service),
) -> ApiKeyCreatedResponse:
    """Create a new API key.

    Requires JWT auth + verified email.
    The full token is returned ONLY in this response.
    """
    # Parse expires_at from the raw value in the DTO
    expires_at: Optional[datetime] = None
    if body.expires_at is not None:
        expires_at = parse_datetime(body.expires_at)
        if expires_at is None:
            raise ValidationError(
                "expires_at must be ISO 8601 or Unix epoch seconds",
                field="expires_at",
            )
        if expires_at <= datetime.now(timezone.utc):
            raise ValidationError(
                "expires_at must be in the future", field="expires_at"
            )

    key_doc, raw_token = await api_key_service.create(
        name=body.name,
        scopes=body.scopes,
        user_id=user.user_id,
        email_verified=user.email_verified,
        description=body.description,
        expires_at=expires_at,
    )

    return ApiKeyCreatedResponse(
        id=str(key_doc.id),
        name=key_doc.name,
        description=key_doc.description,
        scopes=key_doc.scopes,
        created_at=to_unix_timestamp(key_doc.created_at),
        expires_at=to_unix_timestamp(key_doc.expires_at),
        revoked=key_doc.revoked,
        token_prefix=key_doc.token_prefix,
        token=raw_token,
    )


@router.get("/keys")
@limiter.limit("60 per minute")
async def list_api_keys(
    request: Request,
    user: CurrentUser = Depends(require_auth),
    api_key_service: ApiKeyService = Depends(get_api_key_service),
) -> ApiKeysListResponse:
    """List all API keys for the authenticated user.

    Returns both active and revoked keys; the full token is never returned.
    """
    keys = await api_key_service.list_by_user(user.user_id)
    return ApiKeysListResponse(
        keys=[
            ApiKeyResponse(
                id=str(k.id),
                name=k.name,
                description=k.description,
                scopes=k.scopes,
                created_at=to_unix_timestamp(k.created_at),
                expires_at=to_unix_timestamp(k.expires_at),
                revoked=k.revoked,
                token_prefix=k.token_prefix,
            )
            for k in keys
        ]
    )


@router.delete("/keys/{key_id}")
@limiter.limit("30 per minute")
async def delete_api_key(
    request: Request,
    key_id: str,
    revoke: bool = Query(default=False),
    user: CurrentUser = Depends(require_auth),
    api_key_service: ApiKeyService = Depends(get_api_key_service),
) -> ApiKeyActionResponse:
    """Delete (hard) or revoke (soft) an API key.

    ``?revoke=true`` marks the key as revoked but preserves the record.
    Default (``?revoke=false``) permanently deletes the key.
    """
    try:
        key_oid = ObjectId(key_id)
    except Exception:
        raise NotFoundError("key not found or access denied")

    ok = await api_key_service.revoke(user.user_id, key_oid, hard_delete=not revoke)
    if not ok:
        raise NotFoundError("key not found or access denied")

    return ApiKeyActionResponse(success=True, action="revoked" if revoke else "deleted")
