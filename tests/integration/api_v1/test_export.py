"""Tests for GET /api/v1/export."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from dependencies import get_current_user, get_export_service

from .conftest import _build_test_app, _make_api_key_doc, _make_user


class TestExport:
    def test_export_json_returns_correct_content_type(self):
        mock_svc = AsyncMock()
        mock_svc.export = AsyncMock(
            return_value=(b'{"data": []}', "application/json", "stats.json")
        )

        application = _build_test_app(
            {get_current_user: lambda: None, get_export_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.get("/api/v1/export?format=json&scope=anon&short_code=abc123")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        assert "content-disposition" in resp.headers

    def test_export_missing_format_returns_422(self):
        application = _build_test_app(
            {get_current_user: lambda: None, get_export_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/export?scope=anon&short_code=abc123")

        # Missing required `format` field → Pydantic validation → 422
        assert resp.status_code == 422

    def test_export_invalid_format_returns_422(self):
        application = _build_test_app(
            {get_current_user: lambda: None, get_export_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/export?format=pdf&scope=anon&short_code=abc123")

        assert resp.status_code == 422

    def test_export_api_key_missing_scope_returns_403(self):
        key_doc = _make_api_key_doc(scopes=["shorten:create"])
        user = _make_user(api_key_doc=key_doc)

        application = _build_test_app(
            {get_current_user: lambda: user, get_export_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/export?format=json&scope=anon&short_code=abc123")

        assert resp.status_code == 403
