"""Tests for GET /api/v1/stats."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from dependencies import get_current_user, get_stats_service

from .conftest import _build_test_app, _make_api_key_doc, _make_user

_SUMMARY = {
    "total_clicks": 42,
    "unique_clicks": 20,
    "first_click": "2024-01-01T00:00:00+00:00",
    "last_click": "2024-01-07T00:00:00+00:00",
    "avg_redirection_time": 1.5,
}
_TIME_BUCKET_INFO = {
    "strategy": "daily",
    "mongo_format": "%Y-%m-%d",
    "display_format": "%Y-%m-%d",
    "timezone": "UTC",
}
_BASE_STATS_RESULT = {
    "timezone": "UTC",
    "group_by": ["time"],
    "filters": {},
    "time_range": {
        "start_date": "2024-01-01T00:00:00+00:00",
        "end_date": "2024-01-08T00:00:00+00:00",
    },
    "summary": _SUMMARY,
    "metrics": {},
    "generated_at": "2024-01-08T00:00:00+00:00",
    "api_version": "v1",
}


class TestStats:
    _STATS_RESULT = {
        **_BASE_STATS_RESULT,
        "scope": "anon",
        "short_code": "abc123",
        "time_bucket_info": _TIME_BUCKET_INFO,
    }

    def test_stats_anon_scope(self):
        mock_svc = AsyncMock()
        mock_svc.query = AsyncMock(return_value=self._STATS_RESULT)

        application = _build_test_app(
            {get_current_user: lambda: None, get_stats_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.get("/api/v1/stats?scope=anon&short_code=abc123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["scope"] == "anon"
        assert body["summary"]["total_clicks"] == 42
        assert "time_bucket_info" in body
        assert body["time_bucket_info"]["strategy"] == "daily"

    def test_stats_all_scope_with_auth(self):
        user = _make_user()
        mock_svc = AsyncMock()
        mock_svc.query = AsyncMock(return_value={**_BASE_STATS_RESULT, "scope": "all"})

        application = _build_test_app(
            {get_current_user: lambda: user, get_stats_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.get("/api/v1/stats?scope=all")

        assert resp.status_code == 200

    def test_stats_invalid_scope_returns_422(self):
        application = _build_test_app(
            {get_current_user: lambda: None, get_stats_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/stats?scope=invalid_value")

        assert resp.status_code == 422

    def test_stats_api_key_missing_scope_returns_403(self):
        key_doc = _make_api_key_doc(scopes=["shorten:create"])
        user = _make_user(api_key_doc=key_doc)

        application = _build_test_app(
            {get_current_user: lambda: user, get_stats_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/stats?scope=anon&short_code=abc123")

        assert resp.status_code == 403
