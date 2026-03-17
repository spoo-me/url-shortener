"""
Integration tests for click tracking behaviour on the redirect route.

Tests verify that track_click is called with correct arguments on GET,
skipped on HEAD, and that various error scenarios (bad UA, bot block,
unexpected crash) are handled gracefully.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/")

from config import AppSettings
from dependencies import get_click_service, get_url_service
from errors import ForbiddenError, ValidationError
from infrastructure.cache.url_cache import UrlCacheData
from middleware.error_handler import register_error_handlers
from middleware.rate_limiter import limiter
from routes.redirect_routes import router as redirect_router

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static"
)


# ── Helpers ──────────────────────────────────────────────────────────────────


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

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
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
    password_hash: Optional[str] = None,
    block_bots: bool = False,
    max_clicks: Optional[int] = None,
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


def _mock_url_service(url_data: UrlCacheData, schema: str = "v2") -> MagicMock:
    svc = MagicMock()
    svc.resolve = AsyncMock(return_value=(url_data, schema))
    return svc


def _mock_click_service() -> MagicMock:
    svc = MagicMock()
    svc.track_click = AsyncMock(return_value=None)
    return svc


# ── Click tracking on GET ────────────────────────────────────────────────────


def test_click_tracked_on_redirect():
    """GET /{code} should call track_click and still redirect."""
    url_data = _make_url_cache(long_url="https://example.com/target")
    url_svc = _mock_url_service(url_data)
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False, raise_server_exceptions=False) as c:
        resp = c.get("/abc1234", headers={"User-Agent": "Mozilla/5.0"})
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com/target"
    click_svc.track_click.assert_called_once()


def test_click_not_tracked_on_head():
    """HEAD /{code} should NOT call track_click."""
    url_data = _make_url_cache(long_url="https://example.com")
    url_svc = _mock_url_service(url_data)
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False, raise_server_exceptions=False) as c:
        resp = c.head("/abc1234")
    assert resp.status_code == 302
    click_svc.track_click.assert_not_called()


def test_click_not_tracked_on_password_page():
    """GET /{code} for a password-protected URL (no password supplied) should NOT track click."""
    url_data = _make_url_cache(password_hash="$2b$12$hashed")
    url_svc = _mock_url_service(url_data)
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/abc1234")
    assert resp.status_code == 401  # password page
    click_svc.track_click.assert_not_called()


def test_click_bad_user_agent_skips_but_redirects():
    """ValidationError from track_click (bad UA) should skip analytics but still redirect."""
    url_data = _make_url_cache(long_url="https://example.com")
    url_svc = _mock_url_service(url_data)
    click_svc = MagicMock()
    click_svc.track_click = AsyncMock(side_effect=ValidationError("bad UA"))
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False, raise_server_exceptions=False) as c:
        resp = c.get("/abc1234", headers={"User-Agent": ""})
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com"


def test_click_bot_blocked_returns_403():
    """ForbiddenError from track_click (bot blocked) should return 403 JSON, no redirect."""
    url_data = _make_url_cache(
        schema="v1", long_url="https://example.com", block_bots=True
    )
    url_svc = _mock_url_service(url_data, schema="v1")
    click_svc = MagicMock()
    click_svc.track_click = AsyncMock(
        side_effect=ForbiddenError("bots not allowed on this URL")
    )
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/abc123", headers={"User-Agent": "Googlebot/2.1"})
    assert resp.status_code == 403
    assert "text/html" in resp.headers["content-type"]


def test_click_track_receives_correct_context():
    """Verify track_click receives url_data, short_code, schema, and other kwargs."""
    url_data = _make_url_cache(alias="mycode", long_url="https://example.com")
    url_svc = _mock_url_service(url_data, schema="v2")
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False, raise_server_exceptions=False) as c:
        c.get(
            "/mycode",
            headers={
                "User-Agent": "Mozilla/5.0 (Test)",
                "Referer": "https://referrer.com",
            },
        )
    click_svc.track_click.assert_called_once()
    kwargs = click_svc.track_click.call_args.kwargs
    assert kwargs["url_data"] is url_data
    assert kwargs["short_code"] == "mycode"
    assert kwargs["schema"] == "v2"
    assert kwargs["is_emoji"] is False
    assert kwargs["user_agent"] == "Mozilla/5.0 (Test)"
    assert kwargs["referrer"] == "https://referrer.com"


def test_click_error_does_not_crash_redirect():
    """Unexpected exception from track_click should be swallowed — still redirects."""
    url_data = _make_url_cache(long_url="https://example.com/safe")
    url_svc = _mock_url_service(url_data)
    click_svc = MagicMock()
    click_svc.track_click = AsyncMock(side_effect=RuntimeError("DB connection lost"))
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False, raise_server_exceptions=False) as c:
        resp = c.get("/abc1234", headers={"User-Agent": "Mozilla/5.0"})
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com/safe"


def test_click_tracked_with_user_agent_header():
    """The User-Agent header value should be passed to track_click."""
    url_data = _make_url_cache(long_url="https://example.com")
    url_svc = _mock_url_service(url_data)
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    custom_ua = "CustomBrowser/1.0 (Linux; x86_64)"
    with TestClient(app, follow_redirects=False, raise_server_exceptions=False) as c:
        c.get("/abc1234", headers={"User-Agent": custom_ua})
    kwargs = click_svc.track_click.call_args.kwargs
    assert kwargs["user_agent"] == custom_ua


def test_click_tracked_with_referer_header():
    """The Referer header value should be passed to track_click."""
    url_data = _make_url_cache(long_url="https://example.com")
    url_svc = _mock_url_service(url_data)
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False, raise_server_exceptions=False) as c:
        c.get("/abc1234", headers={"Referer": "https://twitter.com/status/123"})
    kwargs = click_svc.track_click.call_args.kwargs
    assert kwargs["referrer"] == "https://twitter.com/status/123"


def test_click_tracked_with_none_referer_when_absent():
    """When no Referer header is present, track_click should receive referrer=None."""
    url_data = _make_url_cache(long_url="https://example.com")
    url_svc = _mock_url_service(url_data)
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False, raise_server_exceptions=False) as c:
        c.get("/abc1234", headers={"User-Agent": "Mozilla/5.0"})
    kwargs = click_svc.track_click.call_args.kwargs
    assert kwargs["referrer"] is None


def test_click_emoji_schema_sets_is_emoji_true():
    """When schema is 'emoji', track_click should receive is_emoji=True."""
    url_data = _make_url_cache(
        alias="smile123", schema="emoji", long_url="https://example.com"
    )
    url_svc = _mock_url_service(url_data, schema="emoji")
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False, raise_server_exceptions=False) as c:
        c.get("/smile123", headers={"User-Agent": "Mozilla/5.0"})
    kwargs = click_svc.track_click.call_args.kwargs
    assert kwargs["is_emoji"] is True
    assert kwargs["schema"] == "emoji"


def test_redirect_sets_noindex_nofollow_header():
    """Redirect response should include X-Robots-Tag: noindex, nofollow."""
    url_data = _make_url_cache(long_url="https://example.com")
    url_svc = _mock_url_service(url_data)
    click_svc = _mock_click_service()
    app = _build_test_app(
        {get_url_service: lambda: url_svc, get_click_service: lambda: click_svc}
    )
    with TestClient(app, follow_redirects=False, raise_server_exceptions=False) as c:
        resp = c.get("/abc1234")
    assert resp.headers.get("x-robots-tag") == "noindex, nofollow"
