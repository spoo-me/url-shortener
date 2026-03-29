"""
Integration tests for the redirect and legacy URL shortener routes.

Uses the _build_test_app pattern from test_api_v1.py — no real infrastructure needed.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/")

from config import AppSettings
from dependencies import get_click_service, get_url_service
from errors import (
    ForbiddenError,
    GoneError,
    NotFoundError,
    ValidationError,
)
from infrastructure.cache.url_cache import UrlCacheData
from middleware.error_handler import register_error_handlers
from middleware.rate_limiter import limiter
from routes.redirect_routes import router as redirect_router

# ── Helpers ──────────────────────────────────────────────────────────────────

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static"
)


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
    if os.path.isdir(_STATIC_DIR):
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
    app.include_router(redirect_router)
    app.dependency_overrides.update(overrides)
    return app


def _make_url_cache(
    alias: str = "abc1234",
    long_url: str = "https://example.com",
    schema: str = "v2",
    password_hash: str | None = None,
    block_bots: bool = False,
    max_clicks: int | None = None,
    total_clicks: int = 0,
    url_status: str = "ACTIVE",
) -> UrlCacheData:
    return UrlCacheData(
        _id="507f1f77bcf86cd799439011",
        alias=alias,
        long_url=long_url,
        block_bots=block_bots,
        password_hash=password_hash,
        expiration_time=None,
        max_clicks=max_clicks,
        url_status=url_status,
        schema_version=schema,
        owner_id=None,
        total_clicks=total_clicks,
    )


# ── Mock services ─────────────────────────────────────────────────────────────


def _mock_url_service(url_data: UrlCacheData, schema: str = "v2"):
    svc = MagicMock()
    svc.resolve = AsyncMock(return_value=(url_data, schema))
    return svc


def _mock_click_service():
    svc = MagicMock()
    svc.track_click = AsyncMock(return_value=None)
    return svc


# ── Redirect tests ────────────────────────────────────────────────────────────


def test_redirect_v2_url():
    url_data = _make_url_cache(long_url="https://example.com/target")
    url_svc = _mock_url_service(url_data)
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False) as client:
        resp = client.get("/abc1234")
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com/target"
    assert resp.headers.get("x-robots-tag") == "noindex, nofollow"


def test_redirect_not_found_returns_404_html():
    url_svc = MagicMock()
    url_svc.resolve = AsyncMock(side_effect=NotFoundError("not found"))
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app) as client:
        resp = client.get("/notexist")
    assert resp.status_code == 404
    assert "text/html" in resp.headers["content-type"]


def test_redirect_blocked_url_returns_403_html():
    url_svc = MagicMock()
    url_svc.resolve = AsyncMock(side_effect=ForbiddenError("blocked"))
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app) as client:
        resp = client.get("/blocked1")
    assert resp.status_code == 403
    assert "text/html" in resp.headers["content-type"]


def test_redirect_expired_url_returns_410_html():
    url_svc = MagicMock()
    url_svc.resolve = AsyncMock(side_effect=GoneError("expired"))
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app) as client:
        resp = client.get("/expired1")
    assert resp.status_code == 410
    assert "text/html" in resp.headers["content-type"]


def test_redirect_password_protected_no_password_returns_401_html():
    url_data = _make_url_cache(password_hash="$2b$12$hashed")
    url_svc = _mock_url_service(url_data)
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app) as client:
        resp = client.get("/abc1234")
    assert resp.status_code == 401
    assert "text/html" in resp.headers["content-type"]


def test_redirect_v2_wrong_password_returns_401_html():
    url_data = _make_url_cache(password_hash="$2b$12$hashed")
    url_svc = _mock_url_service(url_data)
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False) as client:
        resp = client.get("/abc1234?password=wrongpassword")
    assert resp.status_code == 401
    assert "text/html" in resp.headers["content-type"]


def test_redirect_v1_correct_plaintext_password_redirects():
    url_data = _make_url_cache(
        password_hash="mypassword", schema="v1", long_url="https://example.com"
    )
    url_svc = _mock_url_service(url_data, schema="v1")
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False) as client:
        resp = client.get("/abc123?password=mypassword")
    assert resp.status_code == 302


def test_redirect_bad_user_agent_skips_analytics_but_redirects():
    """ValidationError from click_service = bad UA → skip analytics, still redirect."""
    url_data = _make_url_cache(long_url="https://example.com")
    url_svc = _mock_url_service(url_data)
    click_svc = MagicMock()
    click_svc.track_click = AsyncMock(side_effect=ValidationError("bad UA"))
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False) as client:
        resp = client.get("/abc1234", headers={"User-Agent": ""})
    assert resp.status_code == 302


def test_redirect_bot_blocked_v1_returns_403():
    """ForbiddenError from click_service (v1 bot block) → 403 JSON response."""
    url_data = _make_url_cache(
        schema="v1", long_url="https://example.com", block_bots=True
    )
    url_svc = _mock_url_service(url_data, schema="v1")
    click_svc = MagicMock()
    click_svc.track_click = AsyncMock(side_effect=ForbiddenError("bots not allowed"))
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app) as client:
        resp = client.get("/abc123", headers={"User-Agent": "Googlebot/2.1"})
    assert resp.status_code == 403
    assert "text/html" in resp.headers["content-type"]


def test_redirect_head_skips_click_tracking():
    """HEAD requests skip analytics — click_service.track_click should NOT be called."""
    url_data = _make_url_cache(long_url="https://example.com")
    url_svc = _mock_url_service(url_data)
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False) as client:
        resp = client.head("/abc1234")
    assert resp.status_code == 302
    click_svc.track_click.assert_not_called()


# ── Password form tests ───────────────────────────────────────────────────────


def test_password_form_correct_password_redirects():
    url_data = _make_url_cache(
        password_hash="mypassword", schema="v1", long_url="https://example.com"
    )
    url_svc = _mock_url_service(url_data, schema="v1")
    app = _build_test_app(
        {
            get_url_service: lambda: url_svc,
            get_click_service: lambda: _mock_click_service(),
        }
    )
    with TestClient(app, follow_redirects=False) as client:
        resp = client.post("/abc123/password", data={"password": "mypassword"})
    assert resp.status_code == 302
    assert "password=mypassword" in resp.headers["location"]


def test_password_form_wrong_password_renders_password_html():
    url_data = _make_url_cache(
        password_hash="mypassword", schema="v1", long_url="https://example.com"
    )
    url_svc = _mock_url_service(url_data, schema="v1")
    app = _build_test_app(
        {
            get_url_service: lambda: url_svc,
            get_click_service: lambda: _mock_click_service(),
        }
    )
    with TestClient(app) as client:
        resp = client.post("/abc123/password", data={"password": "wrongpassword"})
    # Re-renders password.html with error — 200 status
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_password_form_url_not_found_returns_400_html():
    url_svc = MagicMock()
    url_svc.resolve = AsyncMock(side_effect=NotFoundError("not found"))
    app = _build_test_app(
        {
            get_url_service: lambda: url_svc,
            get_click_service: lambda: _mock_click_service(),
        }
    )
    with TestClient(app) as client:
        resp = client.post("/noexist/password", data={"password": "pw"})
    assert resp.status_code == 400
    assert "text/html" in resp.headers["content-type"]


def test_password_form_url_not_password_protected_returns_400_html():
    url_data = _make_url_cache(password_hash=None, long_url="https://example.com")
    url_svc = _mock_url_service(url_data)
    app = _build_test_app(
        {
            get_url_service: lambda: url_svc,
            get_click_service: lambda: _mock_click_service(),
        }
    )
    with TestClient(app) as client:
        resp = client.post("/abc1234/password", data={"password": "pw"})
    assert resp.status_code == 400
    assert "text/html" in resp.headers["content-type"]
