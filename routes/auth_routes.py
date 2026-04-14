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
GET  /auth/device/login      → device auth initiation + consent
POST /auth/device/consent    → consent form submission
GET  /auth/device/callback   → code delivery page for extensions
POST /auth/device/token      → exchange code for JWT tokens
POST /auth/device/refresh    → refresh app tokens (body-based)
POST /auth/device/revoke     → revoke app access
"""

from __future__ import annotations

import secrets
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from dependencies import (
    AuthUser,
    JwtUser,
    OptionalUser,
    get_app_grant_repo,
    get_auth_service,
)
from errors import AuthenticationError
from middleware.openapi import AUTH_RESPONSES, ERROR_RESPONSES, PUBLIC_SECURITY
from middleware.rate_limiter import Limits, limiter
from repositories.app_grant_repository import AppGrantRepository
from routes.cookie_helpers import clear_auth_cookies, set_auth_cookies
from schemas.dto.requests.auth import (
    DeviceRefreshRequest,
    DeviceTokenRequest,
    LoginRequest,
    RegisterRequest,
    RequestPasswordResetRequest,
    ResetPasswordRequest,
    SetPasswordRequest,
    VerifyEmailRequest,
)
from schemas.dto.responses.auth import (
    DeviceRefreshResponse,
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
from schemas.models.app import AppEntry
from services.auth_service import OTP_EXPIRY_SECONDS, AuthService
from shared.generators import generate_secure_token
from shared.ip_utils import get_client_ip
from shared.logging import get_logger
from shared.templates import templates

log = get_logger(__name__)

router = APIRouter(tags=["Authentication"])


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
    result = await auth_service.login(email, body.password)
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
    result = await auth_service.register(email, body.password, user_name, client_ip)
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
        result = await auth_service.refresh_token(refresh_token_str)
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
    user: JwtUser,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Set a password for an OAuth-only account.

    Allows users who signed up via OAuth to add a password so they can
    also log in with email + password. Fails if the user already has a
    password set.

    **Authentication**: Required (JWT only — API keys cannot set passwords)

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

_CSRF_COOKIE_NAME = "_consent_csrf"
_CSRF_TTL_SECONDS = 600
_CSRF_TOKEN_BYTES = 32
_CSRF_HEADER_NAME = "x-requested-with"
_CSRF_HEADER_VALUE = "fetch"
_APP_ID_MAX_LEN = 64


def _get_device_app(request: Request, app_id: str) -> AppEntry | None:
    """Look up an app_id in the registry and return it if it's a live device-auth app."""
    if not app_id or len(app_id) > _APP_ID_MAX_LEN:
        return None
    registry: dict[str, AppEntry] = request.app.state.app_registry
    entry = registry.get(app_id)
    return entry if entry and entry.is_live_device_app() else None


def _validate_redirect_uri(redirect_uri: str, app: AppEntry) -> bool:
    """Return True if redirect_uri is empty or in the app's allowlist."""
    return not redirect_uri or redirect_uri in app.redirect_uris


def _device_error(request: Request, error: str, status_code: int = 400) -> Response:
    """Render the device auth error page."""
    return templates.TemplateResponse(
        request, "device_error.html", {"error": error}, status_code=status_code
    )


def _build_callback_redirect(
    code: str, state: str, redirect_uri: str, app: AppEntry
) -> RedirectResponse:
    """Build the redirect to the callback page or a registered redirect_uri."""
    params = urlencode({"code": code, "state": state})
    if redirect_uri and redirect_uri in app.redirect_uris:
        separator = "&" if "?" in redirect_uri else "?"
        return RedirectResponse(f"{redirect_uri}{separator}{params}", status_code=302)
    return RedirectResponse(f"/auth/device/callback?{params}", status_code=302)


@router.get("/auth/device/login", include_in_schema=False)
@limiter.limit(Limits.DEVICE_AUTH)
async def device_login(
    request: Request,
    user: OptionalUser,
    auth_service: AuthService = Depends(get_auth_service),
    grant_repo: AppGrantRepository = Depends(get_app_grant_repo),
    app_id: str = "",
    redirect_uri: str = "",
    state: str = "",
) -> Response:
    """Initiate the device auth flow with app identification and consent.

    Validates the app_id against the registry. If the user has an existing
    active grant, auto-approves and generates a code. Otherwise shows the
    consent screen.
    """
    app = _get_device_app(request, app_id)
    if not app:
        return _device_error(request, "Unknown or unsupported application")

    if not _validate_redirect_uri(redirect_uri, app):
        return _device_error(request, "Invalid redirect URI for this application")

    if not user:
        params: dict[str, str] = {"app_id": app_id}
        if state:
            params["state"] = state
        if redirect_uri:
            params["redirect_uri"] = redirect_uri
        next_url = f"/auth/device/login?{urlencode(params)}"
        return RedirectResponse(f"/?next={quote(next_url)}", status_code=302)

    # Check for existing active grant (auto-approve)
    grant = await grant_repo.find_active_grant(user.user_id, app_id)
    if grant:
        profile = await auth_service.get_user_profile(str(user.user_id))
        code = await auth_service.create_device_auth_code(
            profile.id, profile.email, app_id=app_id
        )
        return _build_callback_redirect(code, state, redirect_uri, app)

    # No grant: show consent screen
    csrf_token = generate_secure_token(_CSRF_TOKEN_BYTES)
    profile = await auth_service.get_user_profile(str(user.user_id))
    response = templates.TemplateResponse(
        request,
        "device_consent.html",
        {
            "app": app,
            "app_id": app_id,
            "state": state,
            "redirect_uri": redirect_uri,
            "csrf_token": csrf_token,
            "user": profile,
        },
    )
    response.set_cookie(
        _CSRF_COOKIE_NAME,
        csrf_token,
        httponly=True,
        secure=request.app.state.settings.jwt.cookie_secure,
        samesite="strict",
        max_age=_CSRF_TTL_SECONDS,
    )
    return response


@router.post("/auth/device/consent", include_in_schema=False)
@limiter.limit(Limits.DEVICE_AUTH)
async def device_consent_approve(
    request: Request,
    user: JwtUser,
    auth_service: AuthService = Depends(get_auth_service),
    grant_repo: AppGrantRepository = Depends(get_app_grant_repo),
    app_id: str = Form(""),
    state: str = Form(""),
    csrf_token: str = Form(""),
    redirect_uri: str = Form(""),
) -> Response:
    """Handle consent form submission (Allow button)."""
    # CSRF validation
    cookie_csrf = request.cookies.get(_CSRF_COOKIE_NAME)
    if (
        not cookie_csrf
        or not csrf_token
        or not secrets.compare_digest(csrf_token, cookie_csrf)
    ):
        return _device_error(
            request, "Invalid or expired consent session. Please try again.", 403
        )

    app = _get_device_app(request, app_id)
    if not app:
        return _device_error(request, "Unknown or unsupported application")

    if not _validate_redirect_uri(redirect_uri, app):
        return _device_error(request, "Invalid redirect URI for this application")

    # Create grant
    await grant_repo.create_or_reactivate(user.user_id, app_id)
    log.info("app_consent_granted", user_id=str(user.user_id), app_id=app_id)

    # Generate device auth code
    profile = await auth_service.get_user_profile(str(user.user_id))
    code = await auth_service.create_device_auth_code(
        profile.id, profile.email, app_id=app_id
    )

    # Clear CSRF cookie and redirect
    response = _build_callback_redirect(code, state, redirect_uri, app)
    response.delete_cookie(_CSRF_COOKIE_NAME)
    return response


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
    grant_repo: AppGrantRepository = Depends(get_app_grant_repo),
) -> DeviceTokenResponse:
    """Exchange a one-time device auth code for JWT tokens.

    The code is obtained from the callback page after the user authenticates
    on spoo.me. Returns access and refresh tokens for the client.

    **Authentication**: Not required (public endpoint)

    **Rate Limits**: 10/min
    """
    result = await auth_service.exchange_device_code(body.code.strip())

    # Verify the grant is still active (closes the revoke race window)
    if result.app_id:
        grant = await grant_repo.find_active_grant(result.user.id, result.app_id)
        if not grant:
            raise AuthenticationError("app access has been revoked")
        try:
            await grant_repo.touch_last_used(result.user.id, result.app_id)
        except Exception:
            log.warning(
                "touch_last_used_failed",
                user_id=str(result.user.id),
                app_id=result.app_id,
            )

    return DeviceTokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        user=UserProfileResponse.from_user(result.user),
    )


# ── App token refresh ─────────────────────────────────────────────────────────


@router.post(
    "/auth/device/refresh",
    responses=ERROR_RESPONSES,
    openapi_extra=PUBLIC_SECURITY,
    operation_id="refreshDeviceTokens",
    summary="Refresh Device Auth Tokens",
)
@limiter.limit(Limits.TOKEN_REFRESH)
async def device_refresh(
    request: Request,
    body: DeviceRefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
    grant_repo: AppGrantRepository = Depends(get_app_grant_repo),
) -> DeviceRefreshResponse:
    """Refresh an app's JWT tokens using a refresh token.

    Accepts the refresh token in the request body (not cookies) for use
    by external apps (browser extensions, desktop, CLI, bots).  If the
    refresh token contains an ``app_id`` claim, the server verifies the
    app grant is still active — revoked apps cannot refresh.

    **Authentication**: Not required (the refresh token itself is the credential)

    **Rate Limits**: 20/min
    """
    result = await auth_service.refresh_token(body.refresh_token)

    if result.app_id:
        grant = await grant_repo.find_active_grant(result.user.id, result.app_id)
        if not grant:
            raise AuthenticationError("app access has been revoked")
        try:
            await grant_repo.touch_last_used(result.user.id, result.app_id)
        except Exception:
            log.warning(
                "touch_last_used_failed",
                user_id=str(result.user.id),
                app_id=result.app_id,
            )

    return DeviceRefreshResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
    )


# ── App revocation (dashboard action) ────────────────────────────────────────


@router.post("/auth/device/revoke", include_in_schema=False)
@limiter.limit(Limits.DEVICE_AUTH)
async def revoke_app(
    request: Request,
    user: JwtUser,
    auth_service: AuthService = Depends(get_auth_service),
    grant_repo: AppGrantRepository = Depends(get_app_grant_repo),
    app_id: str = Form(""),
) -> Response:
    """Revoke an app's access (soft-delete grant + invalidate tokens).

    Protected against CSRF by requiring the X-Requested-With header,
    which cannot be sent by cross-origin form submissions.
    """
    if request.headers.get(_CSRF_HEADER_NAME) != _CSRF_HEADER_VALUE:
        return JSONResponse({"error": "invalid request"}, status_code=403)

    if not app_id or len(app_id) > _APP_ID_MAX_LEN:
        return JSONResponse({"error": "app_id is required"}, status_code=400)

    revoked = await grant_repo.revoke(user.user_id, app_id)
    if not revoked:
        return JSONResponse({"error": "no active grant found"}, status_code=404)

    # Invalidate device auth tokens bound to this app via the public service method
    await auth_service.revoke_device_tokens(user.user_id, app_id=app_id)

    return JSONResponse({"success": True, "message": f"Access revoked for {app_id}"})
