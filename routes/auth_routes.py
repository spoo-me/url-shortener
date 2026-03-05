"""
Auth routes — /auth/* and redirect shortcuts.

POST /auth/login
POST /auth/register
POST /auth/refresh
POST /auth/logout
GET  /auth/me
POST /auth/set-password
GET  /login            → redirect /
GET  /register         → redirect /
GET  /signup           → redirect /
GET  /auth/verify      → HTML template or redirect to /dashboard
POST /auth/send-verification
POST /auth/verify-email
POST /auth/request-password-reset
POST /auth/reset-password
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dependencies import CurrentUser, get_auth_service, require_auth
from errors import AuthenticationError
from middleware.rate_limiter import limiter
from routes.cookie_helpers import clear_auth_cookies, set_auth_cookies
from schemas.dto.requests.auth import (
    LoginRequest,
    RegisterRequest,
    RequestPasswordResetRequest,
    ResetPasswordRequest,
    SetPasswordRequest,
    VerifyEmailRequest,
)
from schemas.dto.responses.auth import (
    LoginResponse,
    LogoutResponse,
    MeResponse,
    RefreshResponse,
    RegisterResponse,
    SendVerificationResponse,
    UserProfileResponse,
    VerifyEmailResponse,
)
from schemas.dto.responses.common import MessageResponse
from services.auth_service import OTP_EXPIRY_SECONDS, AuthService
from shared.ip_utils import get_client_ip

router = APIRouter()

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)


# ── Redirect shortcuts ────────────────────────────────────────────────────────


@router.get("/login")
async def login_redirect() -> RedirectResponse:
    """Redirect /login → / to prevent it being captured as a short-URL alias."""
    return RedirectResponse("/", status_code=302)


@router.get("/register")
async def register_redirect() -> RedirectResponse:
    """Redirect /register → / to prevent it being captured as a short-URL alias."""
    return RedirectResponse("/", status_code=302)


@router.get("/signup")
async def signup_redirect() -> RedirectResponse:
    """Redirect /signup → / to prevent it being captured as a short-URL alias."""
    return RedirectResponse("/", status_code=302)


# ── Auth endpoints ─────────────────────────────────────────────────────────────


@router.post("/auth/login")
@limiter.limit("5 per minute; 50 per day")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """Authenticate with email + password. Sets access and refresh cookies."""
    email = body.email.strip().lower()
    user, access_token, refresh_token = await auth_service.login(email, body.password)
    jwt_cfg = request.app.state.settings.jwt
    set_auth_cookies(response, access_token, refresh_token, jwt_cfg)
    return LoginResponse(
        access_token=access_token,
        user=UserProfileResponse.from_user(user),
    )


@router.post("/auth/register", status_code=201)
@limiter.limit("5 per minute; 50 per day")
async def register(
    request: Request,
    response: Response,
    body: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> RegisterResponse:
    """Register a new user with email + password. Sets access and refresh cookies."""
    email = body.email.strip().lower()
    user_name = (body.user_name or "").strip() or None
    client_ip = get_client_ip(request)
    user, access_token, refresh_token, verification_sent = await auth_service.register(
        email, body.password, user_name, client_ip
    )
    jwt_cfg = request.app.state.settings.jwt
    set_auth_cookies(response, access_token, refresh_token, jwt_cfg)
    return RegisterResponse(
        access_token=access_token,
        user=UserProfileResponse.from_user(user),
        requires_verification=True,
        verification_sent=verification_sent,
    )


@router.post("/auth/refresh")
@limiter.limit("20 per minute")
async def refresh(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    """Rotate access + refresh tokens.

    On invalid/expired refresh token, clears both cookies and returns 401.
    This matches the original Flask behavior exactly.
    """
    jwt_cfg = request.app.state.settings.jwt
    refresh_token_str = request.cookies.get("refresh_token")
    if not refresh_token_str:
        resp = JSONResponse(
            {"error": "missing refresh token", "error_code": "AUTHENTICATION_ERROR"},
            status_code=401,
        )
        clear_auth_cookies(resp, jwt_cfg)
        return resp

    try:
        user, new_access, new_refresh = await auth_service.refresh_token(
            refresh_token_str
        )
    except AuthenticationError as exc:
        resp = JSONResponse(
            {"error": str(exc), "error_code": "AUTHENTICATION_ERROR"},
            status_code=401,
        )
        clear_auth_cookies(resp, jwt_cfg)
        return resp

    resp = JSONResponse(RefreshResponse(access_token=new_access).model_dump())
    set_auth_cookies(resp, new_access, new_refresh, jwt_cfg)
    return resp


@router.post("/auth/logout")
@limiter.limit("60 per hour")
async def logout(
    request: Request,
    response: Response,
) -> LogoutResponse:
    """Clear auth cookies."""
    jwt_cfg = request.app.state.settings.jwt
    clear_auth_cookies(response, jwt_cfg)
    return LogoutResponse(success=True)


@router.get("/auth/me")
@limiter.limit("60 per minute")
async def me(
    request: Request,
    user: CurrentUser = Depends(require_auth),
    auth_service: AuthService = Depends(get_auth_service),
) -> MeResponse:
    """Return the authenticated user's profile."""
    profile = await auth_service.get_user_profile(str(user.user_id))
    return MeResponse(user=UserProfileResponse.from_user(profile))


@router.post("/auth/set-password")
@limiter.limit("5 per minute")
async def set_password(
    request: Request,
    body: SetPasswordRequest,
    user: CurrentUser = Depends(require_auth),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Set a password for an OAuth-only user (no existing password)."""
    await auth_service.set_password(str(user.user_id), body.password)
    return MessageResponse(success=True, message="password set successfully")


@router.get("/auth/verify")
@limiter.limit("60 per minute")
async def verify_page(
    request: Request,
    user: CurrentUser = Depends(require_auth),
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    """Email verification page.

    Redirects to /dashboard if already verified; renders verify.html otherwise.
    """
    profile = await auth_service.get_user_profile(str(user.user_id))
    if profile.email_verified:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(
        "verify.html", {"request": request, "email": profile.email}
    )


@router.post("/auth/send-verification")
@limiter.limit("3 per hour")
async def send_verification(
    request: Request,
    user: CurrentUser = Depends(require_auth),
    auth_service: AuthService = Depends(get_auth_service),
) -> SendVerificationResponse:
    """Send a verification-email OTP to the authenticated user."""
    await auth_service.send_verification(str(user.user_id))
    return SendVerificationResponse(
        success=True,
        message="verification code sent to your email",
        expires_in=OTP_EXPIRY_SECONDS,
    )


@router.post("/auth/verify-email")
@limiter.limit("10 per hour")
async def verify_email(
    request: Request,
    response: Response,
    body: VerifyEmailRequest,
    user: CurrentUser = Depends(require_auth),
    auth_service: AuthService = Depends(get_auth_service),
) -> VerifyEmailResponse:
    """Verify email using an OTP code. Issues new tokens with email_verified=True."""
    new_access, new_refresh = await auth_service.verify_email(
        str(user.user_id), body.code.strip()
    )
    jwt_cfg = request.app.state.settings.jwt
    set_auth_cookies(response, new_access, new_refresh, jwt_cfg)
    return VerifyEmailResponse(
        success=True,
        message="email verified successfully",
        email_verified=True,
    )


@router.post("/auth/request-password-reset")
@limiter.limit("3 per hour")
async def request_password_reset(
    request: Request,
    body: RequestPasswordResetRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Request a password-reset OTP.

    Always returns the same response regardless of whether the email exists
    (timing-safe to prevent user enumeration).
    """
    await auth_service.request_password_reset(body.email.strip().lower())
    return MessageResponse(
        success=True, message="if the email exists, a reset code has been sent"
    )


@router.post("/auth/reset-password")
@limiter.limit("5 per hour")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Reset password using an OTP code."""
    await auth_service.reset_password(
        body.email.strip().lower(), body.code.strip(), body.password
    )
    return MessageResponse(success=True, message="password reset successfully")
