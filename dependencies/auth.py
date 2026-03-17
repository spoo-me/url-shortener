"""
Auth and identity dependency providers.

Resolves the current user from JWT or API key, and provides guards
(require_auth, require_verified_email) used by protected routes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import jwt as pyjwt
import structlog
from bson import ObjectId
from fastapi import Depends, Request

from dependencies.infra import get_db, get_settings
from errors import AuthenticationError, EmailNotVerifiedError, ForbiddenError
from repositories.api_key_repository import ApiKeyRepository
from repositories.user_repository import UserRepository
from schemas.models.api_key import ApiKeyDoc
from shared.crypto import hash_token
from shared.logging import get_logger

log = get_logger(__name__)


@dataclass
class CurrentUser:
    """Resolved identity after auth check.

    ``api_key_doc`` is set when the request was authenticated via API key
    (``Authorization: Bearer spoo_<raw>``).  It is ``None`` for JWT auth.
    Scope checks inspect ``api_key_doc.scopes`` when present.
    """

    user_id: ObjectId
    email_verified: bool
    api_key_doc: Optional[ApiKeyDoc] = field(default=None)


async def get_current_user(
    request: Request,
    db=Depends(get_db),
) -> Optional[CurrentUser]:
    """Resolve the current user from the Authorization header or access_token cookie.

    Auth resolution order (mirrors the existing Flask implementation):
      1. Authorization: Bearer spoo_<raw>  →  API key path
      2. Authorization: Bearer <jwt>        →  JWT path
      3. access_token cookie               →  JWT path
      4. None                              →  anonymous

    Returns None for anonymous requests; never raises.
    """
    settings = get_settings(request)
    jwt_cfg = settings.jwt

    auth_header = request.headers.get("Authorization", "")
    token: Optional[str] = None

    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()

        # ── API key path ──────────────────────────────────────────────────────
        if token.startswith("spoo_"):
            raw = token[len("spoo_") :]
            token_hash = hash_token(raw)
            try:
                key = await ApiKeyRepository(db["api-keys"]).find_by_hash(token_hash)
            except Exception:
                return None

            if key is None or key.revoked:
                return None

            now = datetime.now(timezone.utc)
            if key.expires_at:
                exp = (
                    key.expires_at.replace(tzinfo=timezone.utc)
                    if key.expires_at.tzinfo is None
                    else key.expires_at
                )
                if exp <= now:
                    return None

            try:
                user = await UserRepository(db["users"]).find_by_id(key.user_id)
            except Exception:
                return None

            email_verified = user.email_verified if user else False
            structlog.contextvars.bind_contextvars(
                user_id=str(key.user_id), auth_method="api_key"
            )
            return CurrentUser(
                user_id=key.user_id,
                email_verified=email_verified,
                api_key_doc=key,
            )

    # ── JWT path ──────────────────────────────────────────────────────────────
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        return None

    try:
        algorithm = "RS256" if jwt_cfg.use_rs256 else "HS256"
        verify_key = jwt_cfg.jwt_public_key if jwt_cfg.use_rs256 else jwt_cfg.jwt_secret
        claims = pyjwt.decode(
            token,
            verify_key,
            algorithms=[algorithm],
            issuer=jwt_cfg.jwt_issuer,
            audience=jwt_cfg.jwt_audience,
        )
        # Reject refresh tokens used as access tokens
        if claims.get("type") == "refresh":
            return None
        user_id = ObjectId(claims["sub"])
        email_verified = bool(claims.get("email_verified", False))
        structlog.contextvars.bind_contextvars(user_id=str(user_id), auth_method="jwt")
        return CurrentUser(user_id=user_id, email_verified=email_verified)
    except Exception:
        return None


async def require_auth(
    user: Optional[CurrentUser] = Depends(get_current_user),
) -> CurrentUser:
    """Raise 401 if the request is not authenticated."""
    if user is None:
        raise AuthenticationError("Authentication required")
    return user


async def require_verified_email(
    user: CurrentUser = Depends(require_auth),
) -> CurrentUser:
    """Raise 403 (EMAIL_NOT_VERIFIED) if the user's email is unverified."""
    if not user.email_verified:
        raise EmailNotVerifiedError("Email verification required")
    return user


def check_api_key_scope(user: Optional[CurrentUser], required_scopes: set[str]) -> None:
    """Raise ForbiddenError if an API-key-authenticated user lacks a required scope.

    JWT-authenticated and anonymous requests are not scope-restricted.
    """
    if user is not None and user.api_key_doc is not None:
        if not set(user.api_key_doc.scopes) & required_scopes:
            raise ForbiddenError("Insufficient scope for this operation")
