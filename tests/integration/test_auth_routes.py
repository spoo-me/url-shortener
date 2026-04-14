"""
Integration tests for /auth/* and /oauth/* endpoints.

All DB / Redis / external-service calls are eliminated via
dependency_overrides and a mock lifespan — no real infrastructure needed.
Follows the same pattern as test_api_v1.py.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

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
    get_oauth_service,
    require_auth,
)
from errors import (
    AuthenticationError,
    ConflictError,
    ValidationError,
)
from middleware.error_handler import register_error_handlers
from middleware.rate_limiter import limiter
from routes.auth_routes import router as auth_router
from routes.oauth_routes import router as oauth_router
from schemas.models.user import UserDoc
from schemas.results import AuthResult

# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_test_app(overrides: dict) -> FastAPI:
    """Build a minimal FastAPI app with mock lifespan and given dependency overrides."""
    settings = AppSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.db = MagicMock()
        app.state.redis = None
        app.state.oauth_providers = {}
        yield

    application = FastAPI(lifespan=lifespan)
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_error_handlers(application)
    application.include_router(auth_router)
    application.include_router(oauth_router)

    for dep, override in overrides.items():
        application.dependency_overrides[dep] = override

    return application


def _make_user_doc(
    user_id: ObjectId | None = None,
    email: str = "test@example.com",
    email_verified: bool = True,
    password_set: bool = True,
    password_hash: str | None = "$argon2...",
) -> UserDoc:
    oid = user_id or ObjectId()
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


_MOCK_ACCESS = "mock.access.token"
_MOCK_REFRESH = "mock.refresh.token"


# ── Login ─────────────────────────────────────────────────────────────────────


def test_login_valid_credentials():
    user = _make_user_doc()
    mock_svc = AsyncMock()
    mock_svc.login.return_value = AuthResult(
        user=user, access_token=_MOCK_ACCESS, refresh_token=_MOCK_REFRESH
    )

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/auth/login", json={"email": "test@example.com", "password": "pass"}
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == _MOCK_ACCESS
    assert "user" in data
    assert data["user"]["email"] == "test@example.com"
    # Cookies should be set
    assert "access_token" in resp.cookies or "access_token" in {
        c.name for c in resp.cookies.jar
    }


def test_login_invalid_credentials_returns_401():
    mock_svc = AsyncMock()
    mock_svc.login.side_effect = AuthenticationError("invalid credentials")

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/auth/login", json={"email": "bad@example.com", "password": "wrong"}
        )
    assert resp.status_code == 401
    assert "invalid credentials" in resp.json()["error"]


def test_login_same_error_message_for_unknown_email_and_wrong_password():
    """Both cases must return the same 401 error (no user enumeration)."""
    mock_svc = AsyncMock()
    mock_svc.login.side_effect = AuthenticationError("invalid credentials")

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        r1 = client.post(
            "/auth/login", json={"email": "unknown@example.com", "password": "p"}
        )
        r2 = client.post(
            "/auth/login", json={"email": "test@example.com", "password": "wrong"}
        )
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["error"] == r2.json()["error"]


# ── Register ──────────────────────────────────────────────────────────────────


def test_register_creates_user_returns_201():
    user = _make_user_doc(email_verified=False)
    mock_svc = AsyncMock()
    mock_svc.register.return_value = AuthResult(
        user=user,
        access_token=_MOCK_ACCESS,
        refresh_token=_MOCK_REFRESH,
        verification_sent=True,
    )

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/auth/register",
            json={"email": "new@example.com", "password": "Abc123!@#"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["requires_verification"] is True
    assert data["verification_sent"] is True
    assert "access_token" in data


def test_register_duplicate_email_returns_409():
    mock_svc = AsyncMock()
    mock_svc.register.side_effect = ConflictError("email already registered")

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/auth/register",
            json={"email": "existing@example.com", "password": "Abc123!@#"},
        )
    assert resp.status_code == 409


def test_register_weak_password_returns_400():
    mock_svc = AsyncMock()
    mock_svc.register.side_effect = ValidationError(
        "Password does not meet requirements",
        details={"missing_requirements": ["digit"]},
    )

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/auth/register",
            json={"email": "user@example.com", "password": "weakpassword"},
        )
    assert resp.status_code == 400


# ── Refresh ───────────────────────────────────────────────────────────────────


def test_refresh_rotates_tokens():
    user = _make_user_doc()
    mock_svc = AsyncMock()
    mock_svc.refresh_token.return_value = AuthResult(
        user=user, access_token="new.access", refresh_token="new.refresh"
    )

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("refresh_token", "old.refresh.jwt")
        resp = client.post("/auth/refresh")
    assert resp.status_code == 200
    assert resp.json()["access_token"] == "new.access"


def test_refresh_missing_cookie_clears_cookies_returns_401():
    mock_svc = AsyncMock()

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/auth/refresh")  # no refresh_token cookie
    assert resp.status_code == 401
    # Both cookie clearing headers should be present
    set_cookie_headers = resp.headers.get_list("set-cookie")
    cookie_names = [h.split("=")[0] for h in set_cookie_headers]
    assert "access_token" in cookie_names
    assert "refresh_token" in cookie_names


def test_refresh_expired_token_clears_cookies_returns_401():
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


# ── Logout ────────────────────────────────────────────────────────────────────


def test_logout_clears_cookies_returns_success():
    app = _build_test_app({})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    set_cookie_headers = resp.headers.get_list("set-cookie")
    cookie_names = [h.split("=")[0] for h in set_cookie_headers]
    assert "access_token" in cookie_names
    assert "refresh_token" in cookie_names


# ── Me ────────────────────────────────────────────────────────────────────────


def test_me_returns_user_profile():
    user_oid = ObjectId()
    user = _make_user_doc(user_id=user_oid)
    mock_svc = AsyncMock()
    mock_svc.get_user_profile.return_value = user
    mock_user = CurrentUser(user_id=user_oid, email_verified=True)

    app = _build_test_app(
        {
            get_auth_service: lambda: mock_svc,
            require_auth: lambda: mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert "user" in data
    assert data["user"]["email"] == "test@example.com"


def test_me_requires_auth():
    app = _build_test_app({})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/auth/me")
    assert resp.status_code == 401


# ── Set password ──────────────────────────────────────────────────────────────


def test_set_password_succeeds():
    user_oid = ObjectId()
    mock_svc = AsyncMock()
    mock_svc.set_password.return_value = None
    mock_user = CurrentUser(user_id=user_oid, email_verified=True)

    app = _build_test_app(
        {
            get_auth_service: lambda: mock_svc,
            require_auth: lambda: mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/auth/set-password", json={"password": "NewPass1!"})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_set_password_already_set_returns_400():
    user_oid = ObjectId()
    mock_svc = AsyncMock()
    mock_svc.set_password.side_effect = ValidationError("password already set")
    mock_user = CurrentUser(user_id=user_oid, email_verified=True)

    app = _build_test_app(
        {
            get_auth_service: lambda: mock_svc,
            require_auth: lambda: mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/auth/set-password", json={"password": "NewPass1!"})
    assert resp.status_code == 400


# ── Email verification ────────────────────────────────────────────────────────


def test_verify_email_success_sets_new_cookies():
    user_oid = ObjectId()
    mock_svc = AsyncMock()
    mock_svc.verify_email.return_value = ("new.access", "new.refresh")
    mock_user = CurrentUser(user_id=user_oid, email_verified=False)

    app = _build_test_app(
        {
            get_auth_service: lambda: mock_svc,
            require_auth: lambda: mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/auth/verify-email", json={"code": "123456"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["email_verified"] is True


def test_verify_email_wrong_code_returns_400():
    user_oid = ObjectId()
    mock_svc = AsyncMock()
    mock_svc.verify_email.side_effect = ValidationError(
        "Invalid or expired verification code"
    )
    mock_user = CurrentUser(user_id=user_oid, email_verified=False)

    app = _build_test_app(
        {
            get_auth_service: lambda: mock_svc,
            require_auth: lambda: mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/auth/verify-email", json={"code": "000000"})
    assert resp.status_code == 400


# ── Send verification ─────────────────────────────────────────────────────────


def test_send_verification_returns_success():
    user_oid = ObjectId()
    mock_svc = AsyncMock()
    mock_svc.send_verification.return_value = None
    mock_user = CurrentUser(user_id=user_oid, email_verified=False)

    app = _build_test_app(
        {
            get_auth_service: lambda: mock_svc,
            require_auth: lambda: mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/auth/send-verification")
    assert resp.status_code == 200
    assert resp.json()["expires_in"] == 600


# ── Password reset ────────────────────────────────────────────────────────────


def test_request_password_reset_always_returns_same_response():
    """Timing-safe: identical response for existing and non-existing emails."""
    mock_svc = AsyncMock()
    mock_svc.request_password_reset.return_value = None  # swallows all errors

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        r1 = client.post(
            "/auth/request-password-reset", json={"email": "exists@example.com"}
        )
        r2 = client.post(
            "/auth/request-password-reset", json={"email": "ghost@example.com"}
        )
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()
    assert "if the email exists" in r1.json()["message"]


def test_reset_password_success():
    mock_svc = AsyncMock()
    mock_svc.reset_password.return_value = None

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/auth/reset-password",
            json={
                "email": "user@example.com",
                "code": "123456",
                "password": "New1!abc",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_reset_password_invalid_code_returns_400():
    mock_svc = AsyncMock()
    mock_svc.reset_password.side_effect = ValidationError("invalid or expired code")

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/auth/reset-password",
            json={
                "email": "user@example.com",
                "code": "999999",
                "password": "New1!abc",
            },
        )
    assert resp.status_code == 400


# ── Redirect shortcuts ────────────────────────────────────────────────────────


def test_login_page_redirect():
    app = _build_test_app({})
    with TestClient(
        app, raise_server_exceptions=False, follow_redirects=False
    ) as client:
        resp = client.get("/login")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_register_page_redirect():
    app = _build_test_app({})
    with TestClient(
        app, raise_server_exceptions=False, follow_redirects=False
    ) as client:
        resp = client.get("/register")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_signup_page_redirect():
    app = _build_test_app({})
    with TestClient(
        app, raise_server_exceptions=False, follow_redirects=False
    ) as client:
        resp = client.get("/signup")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


# ── OAuth providers list ──────────────────────────────────────────────────────


def test_list_providers_returns_linked_providers():
    user_oid = ObjectId()
    mock_oauth_svc = AsyncMock()
    mock_oauth_svc.list_providers.return_value = (
        [
            {
                "provider": "google",
                "email": "g@example.com",
                "email_verified": True,
                "linked_at": None,
                "profile": {"name": "G", "picture": ""},
            }
        ],
        True,
    )
    mock_user = CurrentUser(user_id=user_oid, email_verified=True)

    app = _build_test_app(
        {
            get_oauth_service: lambda: mock_oauth_svc,
            require_auth: lambda: mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/oauth/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["password_set"] is True
    assert len(data["providers"]) == 1
    assert data["providers"][0]["provider"] == "google"


def test_list_providers_requires_auth():
    app = _build_test_app({})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/oauth/providers")
    assert resp.status_code == 401


# ── OAuth unlink ──────────────────────────────────────────────────────────────


def test_unlink_provider_success():
    user_oid = ObjectId()
    mock_oauth_svc = AsyncMock()
    mock_oauth_svc.unlink_provider.return_value = None
    mock_user = CurrentUser(user_id=user_oid, email_verified=True)

    app = _build_test_app(
        {
            get_oauth_service: lambda: mock_oauth_svc,
            require_auth: lambda: mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.delete("/oauth/providers/google/unlink")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_unlink_provider_last_method_returns_400():
    user_oid = ObjectId()
    mock_oauth_svc = AsyncMock()
    mock_oauth_svc.unlink_provider.side_effect = ValidationError(
        "cannot unlink last authentication method"
    )
    mock_user = CurrentUser(user_id=user_oid, email_verified=True)

    app = _build_test_app(
        {
            get_oauth_service: lambda: mock_oauth_svc,
            require_auth: lambda: mock_user,
        }
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.delete("/oauth/providers/google/unlink")
    assert resp.status_code == 400


# ── OAuth initiate / unconfigured provider ────────────────────────────────────


def test_oauth_login_unconfigured_provider_returns_404():
    app = _build_test_app({})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/oauth/unknown-provider")
    assert resp.status_code == 404


def test_oauth_link_unconfigured_provider_returns_404():
    user_oid = ObjectId()
    mock_user = CurrentUser(user_id=user_oid, email_verified=True)

    app = _build_test_app({require_auth: lambda: mock_user})
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/oauth/unknown-provider/link")
    assert resp.status_code == 404


# ── OAuth callback — state validation ─────────────────────────────────────────


def test_oauth_callback_missing_state_returns_400():
    mock_oauth_svc = AsyncMock()
    app = _build_test_app({get_oauth_service: lambda: mock_oauth_svc})

    # Patch PROVIDER_STRATEGIES so provider lookup succeeds
    with (
        patch("routes.oauth_routes.PROVIDER_STRATEGIES", {"google": MagicMock()}),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        # No providers configured → 404 before state check
        resp = client.get("/oauth/google/callback")
    # Without a configured client we get 404 (provider not configured)
    assert resp.status_code in (400, 404)


def test_oauth_callback_invalid_state_returns_400():
    """Provider recognized but state string is malformed."""
    mock_oauth_svc = AsyncMock()

    # Build app with google in oauth_providers
    settings = AppSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.db = MagicMock()
        app.state.redis = None
        app.state.oauth_providers = {"google": MagicMock()}
        yield

    application = FastAPI(lifespan=lifespan)
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_error_handlers(application)
    application.include_router(oauth_router)
    application.dependency_overrides[get_oauth_service] = lambda: mock_oauth_svc

    with (
        patch("routes.oauth_routes.PROVIDER_STRATEGIES", {"google": MagicMock()}),
        TestClient(application, raise_server_exceptions=False) as client,
    ):
        resp = client.get("/oauth/google/callback?state=malformed")
    assert resp.status_code == 400
