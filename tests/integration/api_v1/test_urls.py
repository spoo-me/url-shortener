"""Tests for GET /api/v1/urls."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from dependencies import get_current_user, get_url_service, require_auth

from .conftest import _build_test_app, _make_api_key_doc, _make_user


class TestListUrls:
    def test_list_urls_requires_auth(self):
        application = _build_test_app(
            {get_current_user: lambda: None, get_url_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/urls")

        assert resp.status_code == 401

    def test_list_urls_returns_paginated_response_with_camel_case(self):
        user = _make_user()
        list_result = {
            "items": [],
            "page": 1,
            "pageSize": 20,
            "total": 0,
            "hasNext": False,
            "sortBy": "created_at",
            "sortOrder": "descending",
        }
        mock_svc = AsyncMock()
        mock_svc.list_by_owner = AsyncMock(return_value=list_result)

        application = _build_test_app(
            {require_auth: lambda: user, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.get("/api/v1/urls")

        assert resp.status_code == 200
        body = resp.json()
        assert "hasNext" in body
        assert "pageSize" in body
        assert "sortBy" in body

    def test_list_urls_api_key_missing_scope_returns_403(self):
        key_doc = _make_api_key_doc(scopes=["shorten:create"])  # wrong scope
        user = _make_user(api_key_doc=key_doc)

        application = _build_test_app(
            {require_auth: lambda: user, get_url_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/urls")

        assert resp.status_code == 403
