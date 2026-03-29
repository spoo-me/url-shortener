"""Tests for POST /api/v1/claim."""

from __future__ import annotations

from unittest.mock import AsyncMock

from bson import ObjectId
from fastapi.testclient import TestClient

from dependencies import get_current_user, get_url_service
from .conftest import _build_test_app, _make_url_doc, _make_user


class TestClaim:
    def test_claim_success(self):
        user_id = ObjectId()
        user = _make_user(user_id=user_id)
        mock_svc = AsyncMock()
        mock_svc.claim_url = AsyncMock(return_value=True)

        application = _build_test_app(
            {get_current_user: lambda: user, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.post(
                "/api/v1/claim",
                json={"alias": "testme", "manage_token": "valid_token"},
            )

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_svc.claim_url.assert_called_once_with(
            alias="testme", raw_token="valid_token", new_owner_id=user_id
        )

    def test_claim_wrong_token(self):
        user = _make_user()
        mock_svc = AsyncMock()
        mock_svc.claim_url = AsyncMock(return_value=False)

        application = _build_test_app(
            {get_current_user: lambda: user, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/v1/claim",
                json={"alias": "testme", "manage_token": "wrong_token"},
            )

        assert resp.status_code == 403
        assert "detail" in resp.json()

    def test_claim_already_claimed(self):
        # Same logic as wrong token — service returns False
        user = _make_user()
        mock_svc = AsyncMock()
        mock_svc.claim_url = AsyncMock(return_value=False)

        application = _build_test_app(
            {get_current_user: lambda: user, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/v1/claim",
                json={"alias": "claimed", "manage_token": "old_token"},
            )

        assert resp.status_code == 403

    def test_claim_unauthenticated(self):
        application = _build_test_app(
            {get_current_user: lambda: None, get_url_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/v1/claim",
                json={"alias": "testme", "manage_token": "some_token"},
            )

        assert resp.status_code == 401

    def test_shorten_anon_returns_token(self):
        url_doc = _make_url_doc()
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=(url_doc, "secret_token"))

        application = _build_test_app(
            {get_current_user: lambda: None, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.post(
                "/api/v1/shorten", json={"long_url": "https://example.com"}
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["manage_token"] == "secret_token"

    def test_shorten_authed_no_token(self):
        user = _make_user()
        url_doc = _make_url_doc(owner_id=user.user_id)
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=(url_doc, None))

        application = _build_test_app(
            {get_current_user: lambda: user, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.post(
                "/api/v1/shorten", json={"long_url": "https://example.com"}
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["manage_token"] is None
