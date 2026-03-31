"""Tests for PATCH/DELETE /api/v1/urls/{url_id}."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from bson import ObjectId
from fastapi.testclient import TestClient

from dependencies import get_url_service, require_auth
from errors import ForbiddenError, NotFoundError

from .conftest import _build_test_app, _make_api_key_doc, _make_url_doc, _make_user


class TestManagement:
    def test_update_url_returns_200(self):
        user = _make_user()
        url_doc = _make_url_doc(owner_id=user.user_id)
        url_doc.updated_at = datetime(2024, 6, 1, tzinfo=timezone.utc)

        mock_svc = AsyncMock()
        mock_svc.update = AsyncMock(return_value=url_doc)

        application = _build_test_app(
            {require_auth: lambda: user, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.patch(
                f"/api/v1/urls/{ObjectId()}", json={"status": "INACTIVE"}
            )

        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body
        assert "alias" in body
        assert "password_set" in body
        assert "updated_at" in body

    def test_update_url_not_found_returns_404(self):
        user = _make_user()
        mock_svc = AsyncMock()
        mock_svc.update = AsyncMock(side_effect=NotFoundError("URL not found"))

        application = _build_test_app(
            {require_auth: lambda: user, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.patch(
                f"/api/v1/urls/{ObjectId()}", json={"status": "INACTIVE"}
            )

        assert resp.status_code == 404

    def test_update_url_invalid_id_returns_400(self):
        user = _make_user()

        application = _build_test_app(
            {require_auth: lambda: user, get_url_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.patch(
                "/api/v1/urls/not-an-objectid", json={"status": "INACTIVE"}
            )

        assert resp.status_code == 422

    def test_update_status_only_filters_other_fields(self):
        """PATCH .../status pre-filters: only status is passed to the service."""
        user = _make_user()
        url_doc = _make_url_doc(owner_id=user.user_id)
        url_doc.status = "INACTIVE"
        url_doc.updated_at = datetime(2024, 6, 1, tzinfo=timezone.utc)

        mock_svc = AsyncMock()
        mock_svc.update = AsyncMock(return_value=url_doc)

        application = _build_test_app(
            {require_auth: lambda: user, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.patch(
                f"/api/v1/urls/{ObjectId()}/status",
                json={
                    "status": "INACTIVE",
                    "long_url": "https://should-be-ignored.com",
                },
            )

        assert resp.status_code == 200
        call_args = mock_svc.update.call_args
        update_req = call_args[0][1]
        assert update_req.status == "INACTIVE"
        assert update_req.long_url is None

    def test_delete_url_returns_200_with_message(self):
        user = _make_user()
        mock_svc = AsyncMock()
        mock_svc.delete = AsyncMock(return_value=None)

        application = _build_test_app(
            {require_auth: lambda: user, get_url_service: lambda: mock_svc}
        )
        url_id = str(ObjectId())
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.delete(f"/api/v1/urls/{url_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "URL deleted"
        assert body["id"] == url_id

    def test_delete_url_forbidden_returns_403(self):
        user = _make_user()
        mock_svc = AsyncMock()
        mock_svc.delete = AsyncMock(side_effect=ForbiddenError("not owner"))

        application = _build_test_app(
            {require_auth: lambda: user, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.delete(f"/api/v1/urls/{ObjectId()}")

        assert resp.status_code == 403

    def test_update_url_api_key_missing_scope_returns_403(self):
        key_doc = _make_api_key_doc(scopes=["shorten:create"])  # wrong scope
        user = _make_user(api_key_doc=key_doc)

        application = _build_test_app(
            {require_auth: lambda: user, get_url_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.patch(
                f"/api/v1/urls/{ObjectId()}", json={"status": "INACTIVE"}
            )

        assert resp.status_code == 403

    def test_delete_url_api_key_missing_scope_returns_403(self):
        key_doc = _make_api_key_doc(scopes=["shorten:create"])  # wrong scope
        user = _make_user(api_key_doc=key_doc)

        application = _build_test_app(
            {require_auth: lambda: user, get_url_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.delete(f"/api/v1/urls/{ObjectId()}")

        assert resp.status_code == 403
