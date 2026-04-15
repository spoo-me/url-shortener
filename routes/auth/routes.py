"""
Core auth routes — login, register, refresh, logout, profile, set-password.

GET  /login            → redirect /
GET  /register         → redirect /
GET  /signup           → redirect /
POST /auth/login
POST /auth/register
POST /auth/refresh
POST /auth/logout
GET  /auth/me
POST /auth/set-password
"""

from __future__ import annotations

from bson import ObjectId
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from dependencies import (
    AuthUser,
    JwtUser,
    fetch_user_profile,
    get_credential_service,
    get_password_service,
    get_user_repo,
)
from errors import AuthenticationError
from middleware.openapi import AUTH_RESPONSES, ERROR_RESPONSES, PUBLIC_SECURITY
from middleware.rate_limiter import Limits, limiter
from repositories.user_repository import UserRepository
from routes.cookie_helpers import clear_auth_cookies, set_auth_cookies
from schemas.dto.requests.auth import (
    LoginRequest,
    RegisterRequest,
    SetPasswordRequest,
)
from schemas.dto.responses.auth import (
    LoginResponse,
    LogoutResponse,
    MeResponse,
    RefreshResponse,
    RegisterResponse,
    UserProfileResponse,
)
from schemas.dto.responses.common import MessageResponse
from services.auth.credentials import CredentialService
from services.auth.password import PasswordService
from shared.ip_utils import get_client_ip
from shared.logging import get_logger

log = get_logger(__name__)

router = APIRouter()


# ── Redirect shortcuts ────────────────────────────────────────────────────────


@router.get("/login", include_in_schema=False)
async def login_redirect() -> RedirectResponse:
    """Redirect /login → / to prevent it being captured as a short-URL alias."""
    return RedirectResponse("/", status_code=302)


@router.get("/register", include_in_schema=False)
async def register_redirect() -> RedirectResponse:
    """Redirect /register → / to prevent it being captured as a short-URL alias."""
    return RedirectResponse("/", status_code=302)


@router.get("/signup", include_in_schema=False)
async def signup_redirect() -> RedirectResponse:
    """Redirect /signup → / to prevent it being captured as a short-URL alias."""
    return RedirectResponse("/", status_code=302)


# ── Auth endpoints ─────────────────────────────────────────────────────────────


@router.post(
    "/auth/login",
    responses=ERROR_RESPONSES,
    openapi_extra=PUBLIC_SECURITY,
    operation_id="loginUser",
    summary="Login",
)
@limiter.limit(Limits.LOGIN)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    credential_service: CredentialService = Depends(get_credential_service),
) -> LoginResponse:
    """Authenticate with email and password.

    Returns JWT access token and sets secure HTTP-only cookies for both
    access and refresh tokens. The refresh token can be used at
    ``POST /auth/refresh`` to obtain new tokens without re-authenticating.

    **Authentication**: Not required (public endpoint)

    **Rate Limits**: 5/min, 50/day

    **Security**: Returns identical error for wrong email and wrong password
    to prevent user enumeration.
    """
    email = body.email.strip().lower()
    result = await credential_service.login(email, body.password)
    jwt_cfg = request.app.state.settings.jwt
    set_auth_cookies(response, result.access_token, result.refresh_token, jwt_cfg)
    return LoginResponse(
        access_token=result.access_token,
        user=UserProfileResponse.from_user(result.user),
    )


@router.post(
    "/auth/register",
    status_code=201,
    responses=AUTH_RESPONSES,
    openapi_extra=PUBLIC_SECURITY,
    operation_id="registerUser",
    summary="Register",
)
@limiter.limit(Limits.SIGNUP)
async def register(
    request: Request,
    response: Response,
    body: RegisterRequest,
    credential_service: CredentialService = Depends(get_credential_service),
) -> RegisterResponse:
    """Create a new user account with email and password.

    Immediately signs the user in by returning a JWT access token and setting
    secure HTTP-only cookies. A verification email is sent best-effort; the
    ``verification_sent`` field indicates whether it succeeded.

    **Authentication**: Not required (public endpoint)

    **Rate Limits**: 5/min, 50/day

    **Notes**: The account is created even if the verification email fails.
    The user must verify their email before accessing protected resources.
    """
    email = body.email.strip().lower()
    user_name = (body.user_name or "").strip() or None
    client_ip = get_client_ip(request)
    result = await credential_service.register(
        email, body.password, user_name, client_ip
    )
    jwt_cfg = request.app.state.settings.jwt
    set_auth_cookies(response, result.access_token, result.refresh_token, jwt_cfg)
    return RegisterResponse(
        access_token=result.access_token,
        user=UserProfileResponse.from_user(result.user),
        requires_verification=True,
        verification_sent=result.verification_sent,
    )


@router.post(
    "/auth/refresh",
    response_model=RefreshResponse,
    responses=ERROR_RESPONSES,
    openapi_extra=PUBLIC_SECURITY,
    operation_id="refreshTokens",
    summary="Refresh Tokens",
)
@limiter.limit(Limits.TOKEN_REFRESH)
async def refresh(
    request: Request,
    credential_service: CredentialService = Depends(get_credential_service),
) -> Response:
    """Rotate the access and refresh token pair.

    Reads the ``refresh_token`` cookie, validates it, and issues a new
    access/refresh pair. Both cookies are replaced. If the refresh token
    is missing, expired, or invalid, all auth cookies are cleared and a
    401 response is returned.

    **Authentication**: Requires a valid ``refresh_token`` cookie

    **Rate Limits**: 20/min

    **Notes**: The old refresh token is invalidated after use (rotation).
    """
    jwt_cfg = request.app.state.settings.jwt
    refresh_token_str = request.cookies.get("refresh_token")
    if not refresh_token_str:
        resp = JSONResponse(
            {"error": "missing refresh token", "code": "AUTHENTICATION_ERROR"},
            status_code=401,
        )
        clear_auth_cookies(resp, jwt_cfg)
        return resp

    try:
        result = await credential_service.refresh_token(refresh_token_str)
    except AuthenticationError as exc:
        log.info("token_refresh_failed", error=str(exc))
        resp = JSONResponse(
            {
                "error": "invalid or expired refresh token",
                "code": "AUTHENTICATION_ERROR",
            },
            status_code=401,
        )
        clear_auth_cookies(resp, jwt_cfg)
        return resp

    resp = JSONResponse(RefreshResponse(access_token=result.access_token).model_dump())
    set_auth_cookies(resp, result.access_token, result.refresh_token, jwt_cfg)
    return resp


@router.post(
    "/auth/logout",
    operation_id="logout",
    summary="Logout",
)
@limiter.limit(Limits.LOGOUT)
async def logout(
    request: Request,
    response: Response,
) -> LogoutResponse:
    """Log the current user out by clearing auth cookies.

    Removes the ``access_token`` and ``refresh_token`` HTTP-only cookies.
    Always succeeds regardless of whether the user was authenticated.

    **Authentication**: Not required

    **Rate Limits**: 60/hour
    """
    jwt_cfg = request.app.state.settings.jwt
    clear_auth_cookies(response, jwt_cfg)
    return LogoutResponse(success=True)


@router.get(
    "/auth/me",
    responses=ERROR_RESPONSES,
    operation_id="getCurrentUser",
    summary="Get Current User",
)
@limiter.limit(Limits.AUTH_READ)
async def me(
    request: Request,
    user: AuthUser,
    user_repo: UserRepository = Depends(get_user_repo),
) -> MeResponse:
    """Return the authenticated user's full profile.

    Includes email, verification status, linked OAuth providers, plan,
    and profile picture. Useful for populating the UI after login or
    on page load.

    **Authentication**: Required (JWT or API key)

    **Rate Limits**: 60/min
    """
    profile = await fetch_user_profile(user_repo, ObjectId(str(user.user_id)))
    return MeResponse(user=UserProfileResponse.from_user(profile))


@router.post(
    "/auth/set-password",
    responses=ERROR_RESPONSES,
    operation_id="setPassword",
    summary="Set Password",
)
@limiter.limit(Limits.SET_PASSWORD)
async def set_password(
    request: Request,
    body: SetPasswordRequest,
    user: JwtUser,
    password_service: PasswordService = Depends(get_password_service),
) -> MessageResponse:
    """Set a password for an OAuth-only account.

    Allows users who signed up via OAuth to add a password so they can
    also log in with email + password. Fails if the user already has a
    password set.

    **Authentication**: Required (JWT only — API keys cannot set passwords)

    **Rate Limits**: 5/min
    """
    await password_service.set_password(str(user.user_id), body.password)
    return MessageResponse(success=True, message="password set successfully")
