"""
POST /api/v1/claim — claim ownership of an anonymously created URL.

Transfers a URL from anonymous ownership to the authenticated user,
consuming and invalidating the one-time manage_token in the process.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from dependencies import CurrentUser, get_url_service, require_auth
from middleware.rate_limiter import Limits, dynamic_limit, limiter
from services.url_service import UrlService

router = APIRouter(tags=["URL Management"])

_claim_limit, _claim_key = dynamic_limit(Limits.API_AUTHED, Limits.API_AUTHED)


class ClaimUrlRequest(BaseModel):
    alias: str = Field(..., description="The short alias to claim.")
    manage_token: str = Field(..., description="The one-time token returned at creation.")


class ClaimUrlResponse(BaseModel):
    success: bool
    message: str


@router.post(
    "/claim",
    status_code=200,
    operation_id="claimUrl",
    summary="Claim Anonymous URL",
)
@limiter.limit(_claim_limit, key_func=_claim_key)
async def claim_url(
    request: Request,
    body: ClaimUrlRequest,
    user: CurrentUser = Depends(require_auth),
    url_service: UrlService = Depends(get_url_service),
) -> ClaimUrlResponse:
    """
    Transfer ownership of an anonymously created URL to your account.

    The manage_token is single-use and is invalidated immediately on success.
    Returns 403 if the token is wrong, 409 if already claimed, 404 if not found.
    """
    claimed = await url_service.claim_url(
        alias=body.alias,
        raw_token=body.manage_token,
        new_owner_id=user.user_id,
    )
    if not claimed:
        # Don't distinguish between wrong token / already claimed / not found
        # to avoid oracle attacks.
        raise HTTPException(
            status_code=403,
            detail="Invalid token or URL is not claimable.",
        )
    return ClaimUrlResponse(success=True, message="URL successfully claimed.")
