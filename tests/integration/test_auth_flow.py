"""
Integration tests for authentication flows: register -> verify -> login -> refresh -> logout.

All DB / Redis / external-service calls are eliminated via
dependency_overrides and a mock lifespan — no real infrastructure needed.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/")

from config import AppSettings
from dependencies import (
    CurrentUser,
    get_auth_service,
    require_auth,
)
from errors import AuthenticationError, ValidationError
from middleware.error_handler import register_error_handlers
from middleware.rate_limiter import limiter
from routes.auth_routes import router as auth_router
from schemas.models.user import UserDoc

# ── Helpers ──────────────────────────────────────────────────────────────────

_USER_OID = ObjectId()
_EMAIL = "test@example.com"
_PASSWORD = "StrongPass1!"
_ACCESS_TOKEN = "mock.access.token"
_REFRESH_TOKEN = "mock.refresh.token"


def _build_test_app(overrides: dict) -> FastAPI:
    settings = AppSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.db = MagicMock()
        app.state.redis = None
        app.state.email_provider = MagicMock()
        app.state.http_client = MagicMock()
        app.state.oauth_providers = {}
        yield

    app = FastAPI(lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_error_handlers(app)
    app.include_router(auth_router)
    app.dependency_overrides.update(overrides)
    return app


def _make_user_doc(
    user_id: ObjectId | None = None,
    email: str = _EMAIL,
    email_verified: bool = True,
    password_set: bool = True,
    password_hash: str | None = "$argon2...",
) -> UserDoc:
    oid = user_id or _USER_OID
    return UserDoc.from_mongo(
        {
            "_id": oid,
            "email": email,
            "email_verified": email_verified,
            "password_hash": password_hash,
            "password_set": password_set,
            "user_name": "Test User",
            "pfp": None,
            "auth_providers": [],
            "plan": "free",
            "signup_ip": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": "ACTIVE",
        }
    )


# ── Tests ────────────────────────────────────────────────────────────────────


def test_register_then_verify_then_login():
    """Register (201) -> verify-email -> login with same credentials."""
    unverified_user = _make_user_doc(email_verified=False)
    verified_user = _make_user_doc(email_verified=True)

    mock_svc = AsyncMock()
    mock_svc.register.return_value = (
        unverified_user,
        _ACCESS_TOKEN,
        _REFRESH_TOKEN,
        True,
    )
    mock_svc.verify_email.return_value = ("verified.access", "verified.refresh")
    mock_svc.login.return_value = (verified_user, "login.access", "login.refresh")

    # For verify-email and me, user must be authenticated
    unverified_mock_user = CurrentUser(user_id=_USER_OID, email_verified=False)

    # Build app with overrides that change mid-flow
    app = _build_test_app(
        {
            get_auth_service: lambda: mock_svc,
            require_auth: lambda: unverified_mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        # Step 1: Register
        resp = client.post(
            "/auth/register",
            json={"email": _EMAIL, "password": _PASSWORD},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["requires_verification"] is True
        assert data["verification_sent"] is True

        # Step 2: Verify email
        resp = client.post("/auth/verify-email", json={"code": "123456"})
        assert resp.status_code == 200
        assert resp.json()["email_verified"] is True

        # Step 3: Login
        resp = client.post(
            "/auth/login",
            json={"email": _EMAIL, "password": _PASSWORD},
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "login.access"
        assert resp.json()["user"]["email_verified"] is True


def test_register_then_login_unverified():
    """Register -> login succeeds but email_verified=false in response."""
    unverified_user = _make_user_doc(email_verified=False)

    mock_svc = AsyncMock()
    mock_svc.register.return_value = (
        unverified_user,
        _ACCESS_TOKEN,
        _REFRESH_TOKEN,
        True,
    )
    mock_svc.login.return_value = (unverified_user, "login.access", "login.refresh")

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        # Register
        resp = client.post(
            "/auth/register",
            json={"email": _EMAIL, "password": _PASSWORD},
        )
        assert resp.status_code == 201

        # Login (unverified)
        resp = client.post(
            "/auth/login",
            json={"email": _EMAIL, "password": _PASSWORD},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["email_verified"] is False


def test_login_then_refresh_rotates_tokens():
    """Login -> use refresh cookie -> get new tokens."""
    user = _make_user_doc()

    mock_svc = AsyncMock()
    mock_svc.login.return_value = (user, _ACCESS_TOKEN, _REFRESH_TOKEN)
    mock_svc.refresh_token.return_value = (user, "new.access", "new.refresh")

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        # Step 1: Login
        resp = client.post(
            "/auth/login",
            json={"email": _EMAIL, "password": _PASSWORD},
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"] == _ACCESS_TOKEN

        # Step 2: Refresh with cookie
        client.cookies.set("refresh_token", _REFRESH_TOKEN)
        resp = client.post("/auth/refresh")
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "new.access"


def test_login_then_me_returns_profile():
    """Login -> GET /auth/me with access token returns user profile."""
    user = _make_user_doc()

    mock_svc = AsyncMock()
    mock_svc.login.return_value = (user, _ACCESS_TOKEN, _REFRESH_TOKEN)
    mock_svc.get_user_profile.return_value = user

    mock_user = CurrentUser(user_id=_USER_OID, email_verified=True)

    app = _build_test_app(
        {
            get_auth_service: lambda: mock_svc,
            require_auth: lambda: mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        # Step 1: Login
        resp = client.post(
            "/auth/login",
            json={"email": _EMAIL, "password": _PASSWORD},
        )
        assert resp.status_code == 200

        # Step 2: Me
        resp = client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == _EMAIL
        assert data["user"]["email_verified"] is True


def test_login_then_set_password():
    """Login (OAuth user, no password) -> set-password -> success."""
    oauth_user = _make_user_doc(password_set=False, password_hash=None)

    mock_svc = AsyncMock()
    mock_svc.login.return_value = (oauth_user, _ACCESS_TOKEN, _REFRESH_TOKEN)
    mock_svc.set_password.return_value = None

    mock_user = CurrentUser(user_id=_USER_OID, email_verified=True)

    app = _build_test_app(
        {
            get_auth_service: lambda: mock_svc,
            require_auth: lambda: mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        # Step 1: Login
        resp = client.post(
            "/auth/login",
            json={"email": _EMAIL, "password": _PASSWORD},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["password_set"] is False

        # Step 2: Set password
        resp = client.post("/auth/set-password", json={"password": "NewPass1!"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True


def test_register_then_request_reset_then_reset_password():
    """Register -> request-password-reset -> reset-password."""
    user = _make_user_doc(email_verified=False)

    mock_svc = AsyncMock()
    mock_svc.register.return_value = (user, _ACCESS_TOKEN, _REFRESH_TOKEN, True)
    mock_svc.request_password_reset.return_value = None
    mock_svc.reset_password.return_value = None

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        # Step 1: Register
        resp = client.post(
            "/auth/register",
            json={"email": _EMAIL, "password": _PASSWORD},
        )
        assert resp.status_code == 201

        # Step 2: Request password reset
        resp = client.post("/auth/request-password-reset", json={"email": _EMAIL})
        assert resp.status_code == 200
        assert "if the email exists" in resp.json()["message"]

        # Step 3: Reset password
        resp = client.post(
            "/auth/reset-password",
            json={"email": _EMAIL, "code": "123456", "password": "NewPass1!"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True


def test_login_then_logout_clears_cookies():
    """Login -> logout -> cookies cleared."""
    user = _make_user_doc()

    mock_svc = AsyncMock()
    mock_svc.login.return_value = (user, _ACCESS_TOKEN, _REFRESH_TOKEN)

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        # Step 1: Login
        resp = client.post(
            "/auth/login",
            json={"email": _EMAIL, "password": _PASSWORD},
        )
        assert resp.status_code == 200
        # Verify cookies were set
        login_cookies = resp.headers.get_list("set-cookie")
        login_cookie_names = [h.split("=")[0] for h in login_cookies]
        assert "access_token" in login_cookie_names

        # Step 2: Logout
        resp = client.post("/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # Verify cookies were cleared
        logout_cookies = resp.headers.get_list("set-cookie")
        logout_cookie_names = [h.split("=")[0] for h in logout_cookies]
        assert "access_token" in logout_cookie_names
        assert "refresh_token" in logout_cookie_names


def test_full_auth_journey():
    """Comprehensive: Register -> verify -> login -> refresh -> me -> set-password -> logout."""
    unverified_user = _make_user_doc(email_verified=False, password_set=True)
    verified_user = _make_user_doc(email_verified=True, password_set=True)

    mock_svc = AsyncMock()
    mock_svc.register.return_value = (
        unverified_user,
        _ACCESS_TOKEN,
        _REFRESH_TOKEN,
        True,
    )
    mock_svc.verify_email.return_value = ("verified.access", "verified.refresh")
    mock_svc.login.return_value = (verified_user, "login.access", "login.refresh")
    mock_svc.refresh_token.return_value = (
        verified_user,
        "refreshed.access",
        "refreshed.refresh",
    )
    mock_svc.get_user_profile.return_value = verified_user
    mock_svc.set_password.side_effect = ValidationError("password already set")

    unverified_mock_user = CurrentUser(user_id=_USER_OID, email_verified=False)
    verified_mock_user = CurrentUser(user_id=_USER_OID, email_verified=True)

    # Start with unverified user
    app = _build_test_app(
        {
            get_auth_service: lambda: mock_svc,
            require_auth: lambda: unverified_mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        # 1. Register
        resp = client.post(
            "/auth/register",
            json={"email": _EMAIL, "password": _PASSWORD},
        )
        assert resp.status_code == 201

        # 2. Verify email
        resp = client.post("/auth/verify-email", json={"code": "123456"})
        assert resp.status_code == 200
        assert resp.json()["email_verified"] is True

    # Switch to verified user for remaining steps
    app.dependency_overrides[require_auth] = lambda: verified_mock_user

    with TestClient(app, raise_server_exceptions=False) as client:
        # 3. Login
        resp = client.post(
            "/auth/login",
            json={"email": _EMAIL, "password": _PASSWORD},
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "login.access"

        # 4. Refresh
        client.cookies.set("refresh_token", "login.refresh")
        resp = client.post("/auth/refresh")
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "refreshed.access"

        # 5. Me
        resp = client.get("/auth/me")
        assert resp.status_code == 200
        assert resp.json()["user"]["email"] == _EMAIL

        # 6. Set password (already set -> 400)
        resp = client.post("/auth/set-password", json={"password": "AnotherPass1!"})
        assert resp.status_code == 400

        # 7. Logout
        resp = client.post("/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


def test_refresh_with_expired_token_clears_cookies():
    """Refresh with an expired token clears cookies and returns 401."""
    mock_svc = AsyncMock()
    mock_svc.refresh_token.side_effect = AuthenticationError(
        "invalid or expired refresh token"
    )

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("refresh_token", "expired.jwt")
        resp = client.post("/auth/refresh")

    assert resp.status_code == 401
    set_cookie_headers = resp.headers.get_list("set-cookie")
    cookie_names = [h.split("=")[0] for h in set_cookie_headers]
    assert "access_token" in cookie_names
    assert "refresh_token" in cookie_names
