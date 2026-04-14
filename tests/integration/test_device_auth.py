"""Integration tests for the device auth flow endpoints."""

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
from dependencies import get_auth_service, get_current_user
from errors import AuthenticationError
from middleware.error_handler import register_error_handlers
from middleware.rate_limiter import limiter
from routes.auth_routes import router as auth_router
from schemas.models.user import UserDoc
from schemas.results import AuthResult

_USER_OID = ObjectId()
_EMAIL = "test@example.com"


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


def _make_user_doc() -> UserDoc:
    return UserDoc.from_mongo(
        {
            "_id": _USER_OID,
            "email": _EMAIL,
            "email_verified": True,
            "password_set": True,
            "auth_providers": [],
            "plan": "free",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": "ACTIVE",
        }
    )


# ── GET /auth/device/login ───────────────────────────────────────────────────


def test_device_login_unauthenticated_redirects_to_index():
    mock_svc = AsyncMock()
    app = _build_test_app(
        {get_auth_service: lambda: mock_svc, get_current_user: lambda: None}
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/auth/device/login?state=abc", follow_redirects=False)
    assert resp.status_code == 302
    assert "/?next=" in resp.headers["location"]
    assert "state=abc" in resp.headers["location"]


def test_device_login_authenticated_redirects_to_callback():
    from dependencies.auth import CurrentUser

    mock_svc = AsyncMock()
    mock_svc.get_user_profile.return_value = _make_user_doc()
    mock_svc.create_device_auth_code.return_value = "test-code-123"

    user = CurrentUser(user_id=_USER_OID, email_verified=True)
    app = _build_test_app(
        {get_auth_service: lambda: mock_svc, get_current_user: lambda: user}
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/auth/device/login?state=xyz", follow_redirects=False)
    assert resp.status_code == 302
    loc = resp.headers["location"]
    assert "/auth/device/callback" in loc
    assert "code=test-code-123" in loc
    assert "state=xyz" in loc


# ── GET /auth/device/callback ────────────────────────────────────────────────


def test_device_callback_no_code_redirects_home():
    mock_svc = AsyncMock()
    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/auth/device/callback", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_device_callback_with_code_renders_page():
    mock_svc = AsyncMock()
    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/auth/device/callback?code=abc&state=xyz")
    assert resp.status_code == 200
    assert 'data-code="abc"' in resp.text
    assert 'data-state="xyz"' in resp.text


# ── POST /auth/device/token ─────────────────────────────────────────────────


def test_device_token_valid_code():
    mock_svc = AsyncMock()
    user = _make_user_doc()
    mock_svc.exchange_device_code.return_value = AuthResult(
        user=user, access_token="access-tok", refresh_token="refresh-tok"
    )

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post("/auth/device/token", json={"code": "valid-code"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "access-tok"
    assert data["refresh_token"] == "refresh-tok"
    assert data["user"]["email"] == _EMAIL


def test_device_token_invalid_code():
    mock_svc = AsyncMock()
    mock_svc.exchange_device_code.side_effect = AuthenticationError(
        "invalid or expired device auth code"
    )

    app = _build_test_app({get_auth_service: lambda: mock_svc})
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post("/auth/device/token", json={"code": "bad-code"})
    assert resp.status_code == 401
