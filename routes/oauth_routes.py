"""
OAuth routes — /oauth/*

GET    /oauth/providers                           — list linked providers
DELETE /oauth/providers/{provider_name}/unlink    — unlink a provider
GET    /oauth/{provider}                          — initiate OAuth login
GET    /oauth/{provider}/callback                 — handle OAuth callback
GET    /oauth/{provider}/link                     — link provider to existing account

NOTE: The two fixed-prefix paths (/oauth/providers, /oauth/providers/*/unlink)
are registered BEFORE the parametric /{provider} routes to prevent the path
parameter from capturing the literal "providers" segment.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from dependencies import CurrentUser, get_oauth_service, require_auth
from errors import AppError, NotFoundError, ValidationError
from schemas.dto.responses.auth import OAuthProvidersResponse
from schemas.dto.responses.common import MessageResponse
from infrastructure.oauth_clients import (
    PROVIDER_STRATEGIES,
    generate_oauth_state,
    get_oauth_redirect_url,
    verify_oauth_state,
)
from middleware.rate_limiter import limiter
from routes.cookie_helpers import set_auth_cookies
from services.oauth_service import OAuthService
from shared.ip_utils import get_client_ip
from shared.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/oauth")

_DASHBOARD_URL = "/dashboard"


# ── Provider management (fixed paths — must come before parametric routes) ────


@router.get("/providers")
@limiter.limit("60 per minute")
async def list_providers(
    request: Request,
    user: CurrentUser = Depends(require_auth),
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> OAuthProvidersResponse:
    """List all linked OAuth providers for the authenticated user."""
    providers, password_set = await oauth_service.list_providers(str(user.user_id))
    return OAuthProvidersResponse(providers=providers, password_set=password_set)


@router.delete("/providers/{provider_name}/unlink")
@limiter.limit("5 per minute")
async def unlink_provider(
    provider_name: str,
    request: Request,
    user: CurrentUser = Depends(require_auth),
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> MessageResponse:
    """Unlink an OAuth provider from the authenticated user's account."""
    await oauth_service.unlink_provider(str(user.user_id), provider_name)
    return MessageResponse(
        success=True, message=f"{provider_name} unlinked successfully"
    )


# ── OAuth flow (parametric provider routes — after fixed paths) ───────────────


@router.get("/{provider}")
@limiter.limit("10 per minute")
async def oauth_login(
    provider: str,
    request: Request,
) -> Response:
    """Initiate OAuth login flow for the given provider."""
    strategy = PROVIDER_STRATEGIES.get(provider)
    client = getattr(request.app.state, "oauth_providers", {}).get(provider)
    if not strategy or not client:
        raise NotFoundError(f"'{provider}' OAuth not configured")

    log.info("oauth_flow_initiated", provider=provider)
    state = generate_oauth_state(provider, "login")
    redirect_uri = get_oauth_redirect_url(provider, request.app.state.settings.oauth)
    return await client.authorize_redirect(request, redirect_uri, state=state)


@router.get("/{provider}/callback")
@limiter.limit("20 per minute")
async def oauth_callback(
    provider: str,
    request: Request,
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> Response:
    """Handle OAuth callback for the given provider.

    Validates state (CSRF), exchanges the auth code for a token, fetches user
    info, delegates all business logic to OAuthService.handle_callback(), then
    redirects to /dashboard with JWT cookies set.
    """
    strategy = PROVIDER_STRATEGIES.get(provider)
    client = getattr(request.app.state, "oauth_providers", {}).get(provider)
    if not strategy or not client:
        raise NotFoundError(f"'{provider}' OAuth not configured")

    # ── CSRF / state validation ───────────────────────────────────────────────
    state = request.query_params.get("state")
    if not state:
        raise ValidationError("missing state parameter")

    is_valid, state_data, failure_reason = verify_oauth_state(state, provider)
    if not is_valid:
        log.warning("oauth_state_invalid", provider=provider, reason=failure_reason)
        raise ValidationError("invalid state parameter")

    # ── Provider-reported error ───────────────────────────────────────────────
    error = request.query_params.get("error")
    if error:
        error_description = request.query_params.get(
            "error_description", "OAuth authorization failed"
        )
        raise ValidationError(f"OAuth error: {error_description}")

    # ── Token exchange + provider user-info ──────────────────────────────────
    try:
        token = await client.authorize_access_token(request)
        provider_info = strategy.fetch_user_info(client, token)
    except Exception as exc:
        log.error(
            "oauth_callback_failed",
            provider=provider,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise AppError("OAuth authentication failed") from exc

    if not provider_info.get("email"):
        raise ValidationError("email not provided by OAuth provider")

    # ── Delegate to service ───────────────────────────────────────────────────
    action = state_data.get("action", "login")
    client_ip = get_client_ip(request)
    user, access_token, refresh_token = await oauth_service.handle_callback(
        provider, provider_info, action, state_data, client_ip
    )

    # ── Redirect to dashboard with cookies ───────────────────────────────────
    jwt_cfg = request.app.state.settings.jwt
    resp = RedirectResponse(_DASHBOARD_URL, status_code=302)
    set_auth_cookies(resp, access_token, refresh_token, jwt_cfg)
    return resp


@router.get("/{provider}/link")
@limiter.limit("5 per minute")
async def oauth_link(
    provider: str,
    request: Request,
    user: CurrentUser = Depends(require_auth),
) -> Response:
    """Initiate OAuth linking flow to attach a provider to the authenticated account."""
    strategy = PROVIDER_STRATEGIES.get(provider)
    client = getattr(request.app.state, "oauth_providers", {}).get(provider)
    if not strategy or not client:
        raise NotFoundError(f"'{provider}' OAuth not configured")

    log.info("oauth_link_initiated", provider=provider, user_id=str(user.user_id))
    state = generate_oauth_state(provider, "link", user_id=str(user.user_id))
    redirect_uri = get_oauth_redirect_url(provider, request.app.state.settings.oauth)
    return await client.authorize_redirect(request, redirect_uri, state=state)
