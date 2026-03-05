"""
FastAPI dependency providers.

All injectable dependencies are defined here as plain async functions
used with FastAPI's Depends() system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import jwt as pyjwt
from bson import ObjectId
from fastapi import Depends, Request

from config import AppSettings
from errors import AuthenticationError, EmailNotVerifiedError, ForbiddenError
from infrastructure.cache.url_cache import UrlCache
from repositories.api_key_repository import ApiKeyRepository
from repositories.blocked_url_repository import BlockedUrlRepository
from repositories.click_repository import ClickRepository
from repositories.legacy.emoji_url_repository import EmojiUrlRepository
from repositories.legacy.legacy_url_repository import LegacyUrlRepository
from repositories.token_repository import TokenRepository
from repositories.url_repository import UrlRepository
from repositories.user_repository import UserRepository
from schemas.models.api_key import ApiKeyDoc
from services.api_key_service import ApiKeyService
from services.auth_service import AuthService
from services.export.formatters import default_formatters
from services.export.service import ExportService
from services.oauth_service import OAuthService
from services.stats_service import StatsService
from services.url_service import UrlService
from shared.crypto import hash_token
from shared.logging import get_logger

log = get_logger(__name__)


# ── App-level singletons ──────────────────────────────────────────────────────


def get_settings(request: Request) -> AppSettings:
    """Return the AppSettings instance stored on app.state."""
    return request.app.state.settings


async def get_db(request: Request):
    """Return the async MongoDB database from app.state."""
    return request.app.state.db


async def get_redis(request: Request):
    """Return the async Redis client from app.state (may be None if not configured)."""
    return request.app.state.redis


def get_email_provider(request: Request):
    """Return the shared ZeptoMailProvider singleton from app.state."""
    return request.app.state.email_provider


# ── Auth ─────────────────────────────────────────────────────────────────────


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
    settings: AppSettings = request.app.state.settings
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


# ── Repository / Service dependencies ────────────────────────────────────────


async def get_url_service(
    db=Depends(get_db),
    redis=Depends(get_redis),
    settings: AppSettings = Depends(get_settings),
) -> UrlService:
    url_repo = UrlRepository(db["urlsV2"])
    legacy_repo = LegacyUrlRepository(db["urls"])
    emoji_repo = EmojiUrlRepository(db["emojis"])
    blocked_url_repo = BlockedUrlRepository(db["blocked-urls"])
    url_cache = UrlCache(redis, ttl_seconds=settings.redis.redis_ttl_seconds)
    blocked_self_domains = [settings.app_url] if settings.app_url else []
    return UrlService(
        url_repo,
        legacy_repo,
        emoji_repo,
        blocked_url_repo,
        url_cache,
        blocked_self_domains,
    )


async def get_stats_service(db=Depends(get_db)) -> StatsService:
    click_repo = ClickRepository(db["clicks"])
    url_repo = UrlRepository(db["urlsV2"])
    return StatsService(click_repo, url_repo)


async def get_export_service(
    stats: StatsService = Depends(get_stats_service),
) -> ExportService:
    return ExportService(stats, default_formatters())


async def get_api_key_service(db=Depends(get_db)) -> ApiKeyService:
    api_key_repo = ApiKeyRepository(db["api-keys"])
    return ApiKeyService(api_key_repo)


async def get_auth_service(
    db=Depends(get_db),
    settings: AppSettings = Depends(get_settings),
    email=Depends(get_email_provider),
) -> AuthService:
    """Build and return an AuthService for the current request."""
    user_repo = UserRepository(db["users"])
    token_repo = TokenRepository(db["verification-tokens"])
    return AuthService(user_repo, token_repo, email, settings.jwt)


async def get_oauth_service(
    db=Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    email=Depends(get_email_provider),
) -> OAuthService:
    """Build and return an OAuthService for the current request."""
    user_repo = UserRepository(db["users"])
    return OAuthService(user_repo, auth_service, email)
