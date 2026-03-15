"""
Integration tests for redirect routes — the hot path.

GET  /{short_code}          -> resolve + redirect (302)
POST /{short_code}/password -> password form submission

All DB / Redis / external-service calls are eliminated via
dependency_overrides and a mock lifespan — no real infrastructure needed.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/")

from config import AppSettings
from dependencies import get_click_service, get_url_service
from errors import ForbiddenError, GoneError, NotFoundError, ValidationError
from infrastructure.cache.url_cache import UrlCacheData
from middleware.error_handler import register_error_handlers
from middleware.rate_limiter import limiter

from routes.redirect_routes import router as redirect_router

# ── Helpers ──────────────────────────────────────────────────────────────────

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static"
)


def _build_test_app(overrides: dict) -> FastAPI:
    """Build a minimal FastAPI app with mock lifespan and given dependency overrides."""
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

    application = FastAPI(lifespan=lifespan)
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_error_handlers(application)

    if os.path.isdir(_STATIC_DIR):
        application.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    application.include_router(redirect_router)
    application.dependency_overrides.update(overrides)
    return application


def _make_cache_data(**kwargs) -> UrlCacheData:
    """Build a UrlCacheData with sensible defaults; override via kwargs."""
    defaults = dict(
        _id=str(ObjectId()),
        alias="abc123",
        long_url="https://example.com/destination",
        block_bots=False,
        password_hash=None,
        expiration_time=None,
        max_clicks=None,
        url_status="ACTIVE",
        schema_version="v2",
        owner_id=str(ObjectId()),
        total_clicks=0,
    )
    defaults.update(kwargs)
    return UrlCacheData(**defaults)


# ── Tests ────────────────────────────────────────────────────────────────────


def test_redirect_v2_active_url():
    """GET /{code} for an active v2 URL -> 302 with Location header."""
    url_data = _make_cache_data(schema_version="v2")
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v2"))
    mock_click_svc = AsyncMock()
    mock_click_svc.track_click = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/abc123", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["Location"] == url_data.long_url


def test_redirect_v1_active_url():
    """GET /{code} for an active v1 URL -> 302."""
    url_data = _make_cache_data(schema_version="v1", alias="xYz789")
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v1"))
    mock_click_svc = AsyncMock()
    mock_click_svc.track_click = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/xYz789", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["Location"] == url_data.long_url


def test_redirect_emoji_url():
    """GET /{code} for an emoji URL -> 302."""
    url_data = _make_cache_data(schema_version="emoji", alias="\U0001f600\U0001f680")
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "emoji"))
    mock_click_svc = AsyncMock()
    mock_click_svc.track_click = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/%F0%9F%98%80%F0%9F%9A%80", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["Location"] == url_data.long_url


def test_redirect_password_protected_no_password():
    """GET /{code} with password_hash set but no password param -> 401 HTML."""
    url_data = _make_cache_data(password_hash="$2b$12$somebcrypthash")
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v2"))
    mock_click_svc = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/abc123", follow_redirects=False)

    assert resp.status_code == 401
    assert "text/html" in resp.headers.get("content-type", "")


def test_redirect_v2_correct_password_bcrypt():
    """GET /{code}?password=correct with bcrypt hash -> 302 (verify_password mocked)."""
    url_data = _make_cache_data(password_hash="$2b$12$somebcrypthash")
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v2"))
    mock_click_svc = AsyncMock()
    mock_click_svc.track_click = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)

    with patch("routes.redirect_routes.verify_password", return_value=True):
        resp = client.get("/abc123?password=correct", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["Location"] == url_data.long_url


def test_redirect_v1_correct_plaintext_password():
    """GET /{code}?password=secret for v1 plaintext password match -> 302."""
    url_data = _make_cache_data(password_hash="secret", schema_version="v1")
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v1"))
    mock_click_svc = AsyncMock()
    mock_click_svc.track_click = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/abc123?password=secret", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["Location"] == url_data.long_url


def test_redirect_wrong_password():
    """GET /{code}?password=wrong -> 401 HTML password page."""
    url_data = _make_cache_data(password_hash="$2b$12$somebcrypthash")
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v2"))
    mock_click_svc = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)

    with patch("routes.redirect_routes.verify_password", return_value=False):
        resp = client.get("/abc123?password=wrong", follow_redirects=False)

    assert resp.status_code == 401
    assert "text/html" in resp.headers.get("content-type", "")


def test_redirect_blocked_url():
    """resolve raises ForbiddenError -> 403 HTML."""
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(side_effect=ForbiddenError("Blocked"))
    mock_click_svc = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/abc123", follow_redirects=False)

    assert resp.status_code == 403
    assert "text/html" in resp.headers.get("content-type", "")


def test_redirect_expired_url():
    """resolve raises GoneError -> 410 HTML."""
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(side_effect=GoneError("Expired"))
    mock_click_svc = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/abc123", follow_redirects=False)

    assert resp.status_code == 410
    assert "text/html" in resp.headers.get("content-type", "")


def test_redirect_inactive_url():
    """resolve raises GoneError for inactive URL -> 410 HTML."""
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(side_effect=GoneError("Inactive"))
    mock_click_svc = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/someCode", follow_redirects=False)

    assert resp.status_code == 410
    assert "text/html" in resp.headers.get("content-type", "")


def test_redirect_not_found():
    """resolve raises NotFoundError -> 404 HTML."""
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(side_effect=NotFoundError("Not found"))
    mock_click_svc = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/nope42", follow_redirects=False)

    assert resp.status_code == 404
    assert "text/html" in resp.headers.get("content-type", "")


def test_redirect_max_clicks_reached():
    """After max clicks, resolve raises GoneError -> 410."""
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(side_effect=GoneError("Max clicks reached"))
    mock_click_svc = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/abc123", follow_redirects=False)

    assert resp.status_code == 410


def test_redirect_bot_blocked_v1():
    """click_service raises ForbiddenError for bot on v1 -> 403 JSON."""
    url_data = _make_cache_data(schema_version="v1", block_bots=True)
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v1"))
    mock_click_svc = AsyncMock()
    mock_click_svc.track_click = AsyncMock(
        side_effect=ForbiddenError("Bot access denied")
    )

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/abc123", follow_redirects=False)

    assert resp.status_code == 403
    body = resp.json()
    assert body["error_code"] == "403"
    assert "Bot access denied" in body["error_message"]


def test_redirect_bot_blocked_v2():
    """v2 with block_bots, click_service raises ForbiddenError -> 403 JSON."""
    url_data = _make_cache_data(schema_version="v2", block_bots=True)
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v2"))
    mock_click_svc = AsyncMock()
    mock_click_svc.track_click = AsyncMock(
        side_effect=ForbiddenError("Bot access denied")
    )

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/abc123", follow_redirects=False)

    assert resp.status_code == 403
    body = resp.json()
    assert body["error_code"] == "403"


def test_redirect_bad_user_agent_still_redirects():
    """click_service raises ValidationError -> skip analytics, still 302."""
    url_data = _make_cache_data()
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v2"))
    mock_click_svc = AsyncMock()
    mock_click_svc.track_click = AsyncMock(
        side_effect=ValidationError("Bad User-Agent")
    )

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/abc123", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["Location"] == url_data.long_url


def test_redirect_head_request_skips_tracking():
    """HEAD /{code} -> 302, track_click NOT called."""
    url_data = _make_cache_data()
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v2"))
    mock_click_svc = AsyncMock()
    mock_click_svc.track_click = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.head("/abc123", follow_redirects=False)

    assert resp.status_code == 302
    mock_click_svc.track_click.assert_not_called()


def test_redirect_sets_x_robots_tag():
    """Response has X-Robots-Tag: noindex, nofollow."""
    url_data = _make_cache_data()
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v2"))
    mock_click_svc = AsyncMock()
    mock_click_svc.track_click = AsyncMock()

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
            get_click_service: lambda: mock_click_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/abc123", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers.get("X-Robots-Tag") == "noindex, nofollow"


def test_password_form_submit_correct():
    """POST /{code}/password with correct password -> 302 redirect with password param."""
    url_data = _make_cache_data(password_hash="$2b$12$somebcrypthash")
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v2"))

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)

    with patch("routes.redirect_routes.verify_password", return_value=True):
        resp = client.post(
            "/abc123/password",
            data={"password": "correct"},
            follow_redirects=False,
        )

    assert resp.status_code == 302
    assert "/abc123?password=correct" in resp.headers["Location"]


def test_password_form_submit_wrong():
    """POST /{code}/password with wrong password -> 200 HTML (re-render)."""
    url_data = _make_cache_data(password_hash="$2b$12$somebcrypthash")
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v2"))

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)

    with patch("routes.redirect_routes.verify_password", return_value=False):
        resp = client.post(
            "/abc123/password",
            data={"password": "wrong"},
            follow_redirects=False,
        )

    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_password_form_url_not_found():
    """POST /{code}/password for missing URL -> 400 HTML."""
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(side_effect=NotFoundError("Not found"))

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/abc123/password",
        data={"password": "anything"},
        follow_redirects=False,
    )

    assert resp.status_code == 400
    assert "text/html" in resp.headers.get("content-type", "")


def test_password_form_not_password_protected():
    """POST /{code}/password for non-protected URL -> 400 HTML."""
    url_data = _make_cache_data(password_hash=None)
    mock_url_svc = AsyncMock()
    mock_url_svc.resolve = AsyncMock(return_value=(url_data, "v2"))

    app = _build_test_app(
        {
            get_url_service: lambda: mock_url_svc,
        }
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/abc123/password",
        data={"password": "anything"},
        follow_redirects=False,
    )

    assert resp.status_code == 400
    assert "text/html" in resp.headers.get("content-type", "")
