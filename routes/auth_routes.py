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

from dependencies import AuthUser, OptionalUser, get_auth_service
from errors import AuthenticationError
from middleware.openapi import AUTH_RESPONSES, ERROR_RESPONSES, PUBLIC_SECURITY
from middleware.rate_limiter import Limits, limiter
from routes.cookie_helpers import clear_auth_cookies, set_auth_cookies
from schemas.dto.requests.auth import (
    DeviceTokenRequest,
    LoginRequest,
    RegisterRequest,
    RequestPasswordResetRequest,
    ResetPasswordRequest,
    SetPasswordRequest,
    VerifyEmailRequest,
)
from schemas.dto.responses.auth import (
    DeviceTokenResponse,
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
from shared.logging import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["Authentication"])

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)


def _validate_redirect_uri(uri: str, allowed: list[str]) -> str | None:
    """Return the URI if it's in the allowlist, None otherwise."""
    if not uri or not allowed:
        return None
    return uri if uri in allowed else None


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
    auth_service: AuthService = Depends(get_auth_service),
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
    user, access_token, refresh_token = await auth_service.login(email, body.password)
    jwt_cfg = request.app.state.settings.jwt
    set_auth_cookies(response, access_token, refresh_token, jwt_cfg)
    return LoginResponse(
        access_token=access_token,
        user=UserProfileResponse.from_user(user),
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
    auth_service: AuthService = Depends(get_auth_service),
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
    auth_service: AuthService = Depends(get_auth_service),
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
        _user, new_access, new_refresh = await auth_service.refresh_token(
            refresh_token_str
        )
    except AuthenticationError as exc:
        log.warning("token_refresh_failed", error=str(exc))
        resp = JSONResponse(
            {
                "error": "invalid or expired refresh token",
                "code": "AUTHENTICATION_ERROR",
            },
            status_code=401,
        )
        clear_auth_cookies(resp, jwt_cfg)
        return resp

    resp = JSONResponse(RefreshResponse(access_token=new_access).model_dump())
    set_auth_cookies(resp, new_access, new_refresh, jwt_cfg)
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
    auth_service: AuthService = Depends(get_auth_service),
) -> MeResponse:
    """Return the authenticated user's full profile.

    Includes email, verification status, linked OAuth providers, plan,
    and profile picture. Useful for populating the UI after login or
    on page load.

    **Authentication**: Required (JWT or API key)

    **Rate Limits**: 60/min
    """
    profile = await auth_service.get_user_profile(str(user.user_id))
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
    user: AuthUser,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Set a password for an OAuth-only account.

    Allows users who signed up via OAuth to add a password so they can
    also log in with email + password. Fails if the user already has a
    password set.

    **Authentication**: Required (JWT or API key)

    **Rate Limits**: 5/min
    """
    await auth_service.set_password(str(user.user_id), body.password)
    return MessageResponse(success=True, message="password set successfully")


@router.get("/auth/verify", include_in_schema=False)
@limiter.limit(Limits.DASHBOARD_READ)
async def verify_page(
    request: Request,
    user: AuthUser,
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    """Email verification page.

    Redirects to /dashboard if already verified; renders verify.html otherwise.
    """
    profile = await auth_service.get_user_profile(str(user.user_id))
    if profile.email_verified:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(request, "verify.html", {"email": profile.email})


@router.post(
    "/auth/send-verification",
    responses=ERROR_RESPONSES,
    operation_id="sendVerification",
    summary="Send Verification Email",
)
@limiter.limit(Limits.RESEND_VERIFICATION)
async def send_verification(
    request: Request,
    user: AuthUser,
    auth_service: AuthService = Depends(get_auth_service),
) -> SendVerificationResponse:
    """Send a 6-digit OTP verification code to the user's email.

    The code expires after the duration returned in ``expires_in`` (seconds).
    Returns 400 if the user's email is already verified.

    **Authentication**: Required (JWT or API key)

    **Rate Limits**: 1/minute, 3/hour

    **Notes**: Previous unused OTPs are invalidated when a new one is sent.
    """
    await auth_service.send_verification(str(user.user_id))
    return SendVerificationResponse(
        success=True,
        message="verification code sent to your email",
        expires_in=OTP_EXPIRY_SECONDS,
    )


@router.post(
    "/auth/verify-email",
    responses=ERROR_RESPONSES,
    operation_id="verifyEmail",
    summary="Verify Email",
)
@limiter.limit(Limits.EMAIL_VERIFY)
async def verify_email(
    request: Request,
    response: Response,
    body: VerifyEmailRequest,
    user: AuthUser,
    auth_service: AuthService = Depends(get_auth_service),
) -> VerifyEmailResponse:
    """Verify the user's email address using a 6-digit OTP code.

    On success, new JWT tokens are issued with ``email_verified=true`` in the
    claims, and auth cookies are updated. A welcome email is sent best-effort.

    **Authentication**: Required (JWT or API key)

    **Rate Limits**: 10/hour

    **Notes**: The OTP must match the most recently sent code and must not
    be expired. Expired or already-used codes are rejected.
    """
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


@router.post(
    "/auth/request-password-reset",
    openapi_extra=PUBLIC_SECURITY,
    operation_id="requestPasswordReset",
    summary="Request Password Reset",
)
@limiter.limit(Limits.PASSWORD_RESET_REQUEST)
async def request_password_reset(
    request: Request,
    body: RequestPasswordResetRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Request a password-reset OTP to be sent via email.

    Always returns the same success response regardless of whether the
    email is registered. This prevents user enumeration attacks.

    **Authentication**: Not required (public endpoint)

    **Rate Limits**: 3/hour

    **Security**: Timing-safe -- response time is constant whether or not
    the account exists.
    """
    await auth_service.request_password_reset(body.email.strip().lower())
    return MessageResponse(
        success=True, message="if the email exists, a reset code has been sent"
    )


@router.post(
    "/auth/reset-password",
    responses=ERROR_RESPONSES,
    openapi_extra=PUBLIC_SECURITY,
    operation_id="resetPassword",
    summary="Reset Password",
)
@limiter.limit(Limits.PASSWORD_RESET_CONFIRM)
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Reset the account password using a 6-digit OTP code.

    The OTP must have been requested via ``POST /auth/request-password-reset``.
    On success the password is updated immediately and the OTP is consumed.

    **Authentication**: Not required (public endpoint)

    **Rate Limits**: 5/hour

    **Notes**: Expired or already-used OTPs are rejected with a 400 error.
    """
    await auth_service.reset_password(
        body.email.strip().lower(), body.code.strip(), body.password
    )
    return MessageResponse(success=True, message="password reset successfully")


# ── Device auth flow (extensions, apps, CLIs) ────────────────────────────────


@router.get("/auth/device/login", include_in_schema=False)
@limiter.limit(Limits.DEVICE_AUTH)
async def device_login(
    request: Request,
    user: OptionalUser,
    auth_service: AuthService = Depends(get_auth_service),
    redirect_uri: str = "",
    state: str = "",
) -> RedirectResponse:
    """Initiate the device auth flow.

    If the user already has a valid session, generates an auth code and
    redirects to the callback page (or a registered redirect_uri).
    Otherwise, redirects to the login page.
    Used by browser extensions, mobile apps, and other third-party clients.

    The ``state`` parameter is passed through for CSRF protection — the
    client generates it, the server carries it, the client verifies it.
    """
    if user:
        profile = await auth_service.get_user_profile(str(user.user_id))
        code = await auth_service.create_device_auth_code(profile.id, profile.email)
        allowed = request.app.state.settings.device_auth_redirect_uris
        validated_uri = _validate_redirect_uri(redirect_uri, allowed)
        if validated_uri:
            separator = "&" if "?" in validated_uri else "?"
            return RedirectResponse(
                f"{validated_uri}{separator}code={code}&state={state}",
                status_code=302,
            )
        return RedirectResponse(
            f"/auth/device/callback?code={code}&state={state}", status_code=302
        )

    # Preserve params through the login flow
    params = "state=" + state if state else ""
    if redirect_uri:
        params += ("&" if params else "") + f"redirect_uri={redirect_uri}"
    next_url = "/auth/device/login" + (f"?{params}" if params else "")
    return RedirectResponse(f"/?next={next_url}", status_code=302)


@router.get("/auth/device/callback", include_in_schema=False)
@limiter.limit(Limits.DEVICE_AUTH)
async def device_callback(
    request: Request,
    code: str = "",
    state: str = "",
) -> Response:
    """Render the device auth callback page.

    The client reads the auth code and state from data attributes on the page.
    For browser extensions, the content script handles this automatically.
    """
    if not code:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        request, "device_callback.html", {"code": code, "state": state}
    )


@router.post(
    "/auth/device/token",
    responses=ERROR_RESPONSES,
    openapi_extra=PUBLIC_SECURITY,
    operation_id="exchangeDeviceCode",
    summary="Exchange Device Auth Code",
)
@limiter.limit(Limits.DEVICE_TOKEN)
async def device_token(
    request: Request,
    body: DeviceTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> DeviceTokenResponse:
    """Exchange a one-time device auth code for JWT tokens.

    The code is obtained from the callback page after the user authenticates
    on spoo.me. Returns access and refresh tokens for the client.

    **Authentication**: Not required (public endpoint)

    **Rate Limits**: 10/min
    """
    user, access_token, refresh_token = await auth_service.exchange_device_code(
        body.code.strip()
    )
    return DeviceTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserProfileResponse.from_user(user),
    )
