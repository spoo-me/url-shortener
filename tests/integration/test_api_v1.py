"""
Integration tests for /api/v1/* endpoints.

All DB / Redis / external-service calls are eliminated via
dependency_overrides and a mock lifespan — no real infrastructure needed.
Follows the same pattern as test_health.py.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/")

from config import AppSettings
from dependencies import (
    CurrentUser,
    get_api_key_service,
    get_current_user,
    get_export_service,
    get_stats_service,
    get_url_service,
    require_auth,
    require_verified_email,
)
from errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
    register_error_handlers,
)
from middleware.rate_limiter import limiter
from routes.api_v1 import router as api_v1_router
from schemas.models.api_key import ApiKeyDoc
from schemas.models.url import UrlV2Doc

# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_test_app(overrides: dict) -> FastAPI:
    """Build a minimal FastAPI app with mock lifespan and given dependency overrides."""
    settings = AppSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.db = MagicMock()
        app.state.redis = None
        yield

    application = FastAPI(lifespan=lifespan)
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_error_handlers(application)
    application.include_router(api_v1_router)

    for dep, override in overrides.items():
        application.dependency_overrides[dep] = override

    return application


def _make_url_doc(
    alias: str = "testme", owner_id: Optional[ObjectId] = None
) -> UrlV2Doc:
    oid = owner_id or ObjectId()
    return UrlV2Doc(
        **{
            "_id": ObjectId(),
            "alias": alias,
            "owner_id": oid,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "long_url": "https://example.com/long",
            "status": "ACTIVE",
            "private_stats": False,
        }
    )


def _make_user(
    user_id: Optional[ObjectId] = None,
    email_verified: bool = True,
    api_key_doc: Optional[ApiKeyDoc] = None,
) -> CurrentUser:
    return CurrentUser(
        user_id=user_id or ObjectId(),
        email_verified=email_verified,
        api_key_doc=api_key_doc,
    )


def _make_api_key_doc(
    user_id: Optional[ObjectId] = None, scopes: Optional[list] = None
) -> ApiKeyDoc:
    return ApiKeyDoc(
        **{
            "_id": ObjectId(),
            "user_id": user_id or ObjectId(),
            "token_prefix": "AbCdEfGh",
            "token_hash": "testhash",
            "name": "Test Key",
            "scopes": scopes or ["shorten:create"],
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "revoked": False,
        }
    )


# ── POST /api/v1/shorten ─────────────────────────────────────────────────────


class TestShorten:
    def test_shorten_anon_returns_201(self):
        url_doc = _make_url_doc()
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=url_doc)

        application = _build_test_app(
            {get_current_user: lambda: None, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.post(
                "/api/v1/shorten", json={"long_url": "https://example.com"}
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["alias"] == url_doc.alias
        assert "short_url" in body
        assert body["status"] == "ACTIVE"

    def test_shorten_with_alias(self):
        url_doc = _make_url_doc(alias="myalias")
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=url_doc)

        application = _build_test_app(
            {get_current_user: lambda: None, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.post(
                "/api/v1/shorten",
                json={"long_url": "https://example.com", "alias": "myalias"},
            )

        assert resp.status_code == 201
        assert resp.json()["alias"] == "myalias"

    def test_shorten_api_key_missing_scope_returns_403(self):
        key_doc = _make_api_key_doc(scopes=["stats:read"])  # wrong scope
        user = _make_user(api_key_doc=key_doc)

        application = _build_test_app(
            {get_current_user: lambda: user, get_url_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/v1/shorten", json={"long_url": "https://example.com"}
            )

        assert resp.status_code == 403

    def test_shorten_api_key_admin_scope(self):
        user_id = ObjectId()
        url_doc = _make_url_doc(owner_id=user_id)
        key_doc = _make_api_key_doc(user_id=user_id, scopes=["admin:all"])
        user = _make_user(user_id=user_id, api_key_doc=key_doc)

        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=url_doc)

        application = _build_test_app(
            {get_current_user: lambda: user, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.post(
                "/api/v1/shorten", json={"long_url": "https://example.com"}
            )

        assert resp.status_code == 201

    def test_shorten_missing_long_url_returns_422(self):
        application = _build_test_app(
            {get_current_user: lambda: None, get_url_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.post("/api/v1/shorten", json={})

        assert resp.status_code == 422

    def test_shorten_validation_error_returns_400(self):
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(side_effect=ValidationError("invalid URL"))

        application = _build_test_app(
            {get_current_user: lambda: None, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/v1/shorten", json={"long_url": "https://example.com"}
            )

        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_shorten_conflict_returns_409(self):
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(side_effect=ConflictError("alias taken"))

        application = _build_test_app(
            {get_current_user: lambda: None, get_url_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/v1/shorten",
                json={"long_url": "https://example.com", "alias": "taken"},
            )

        assert resp.status_code == 409


# ── GET /api/v1/urls ─────────────────────────────────────────────────────────


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


# ── PATCH/DELETE /api/v1/urls/{url_id} ───────────────────────────────────────


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

        assert resp.status_code == 400

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


# ── GET /api/v1/stats ─────────────────────────────────────────────────────────


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
    "time_range": {"start_date": "2024-01-01T00:00:00+00:00", "end_date": "2024-01-08T00:00:00+00:00"},
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
        mock_svc.query = AsyncMock(
            return_value={**_BASE_STATS_RESULT, "scope": "all"}
        )

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


# ── GET /api/v1/export ───────────────────────────────────────────────────────


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


# ── API Keys ─────────────────────────────────────────────────────────────────


class TestApiKeys:
    def test_create_key_returns_201_with_token(self):
        user = _make_user(email_verified=True)
        key_doc = _make_api_key_doc(user_id=user.user_id)

        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(return_value=(key_doc, "spoo_rawtoken123"))

        application = _build_test_app(
            {
                require_verified_email: lambda: user,
                get_api_key_service: lambda: mock_svc,
            }
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.post(
                "/api/v1/keys",
                json={"name": "Test Key", "scopes": ["shorten:create"]},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["token"] == "spoo_rawtoken123"
        assert body["token_prefix"] == "AbCdEfGh"
        assert "id" in body

    def test_create_key_unverified_email_returns_403(self):
        user = _make_user(email_verified=False)

        application = _build_test_app(
            {get_current_user: lambda: user, get_api_key_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/v1/keys",
                json={"name": "Test Key", "scopes": ["shorten:create"]},
            )

        assert resp.status_code == 403
        assert resp.json()["code"] == "EMAIL_NOT_VERIFIED"

    def test_create_key_requires_auth(self):
        application = _build_test_app(
            {get_current_user: lambda: None, get_api_key_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/v1/keys",
                json={"name": "Test Key", "scopes": ["shorten:create"]},
            )

        assert resp.status_code == 401

    def test_list_keys_requires_auth(self):
        application = _build_test_app(
            {get_current_user: lambda: None, get_api_key_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/keys")

        assert resp.status_code == 401

    def test_list_keys_returns_keys_without_token(self):
        user = _make_user()
        key_doc = _make_api_key_doc(user_id=user.user_id)

        mock_svc = AsyncMock()
        mock_svc.list_by_user = AsyncMock(return_value=[key_doc])

        application = _build_test_app(
            {require_auth: lambda: user, get_api_key_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.get("/api/v1/keys")

        assert resp.status_code == 200
        body = resp.json()
        assert "keys" in body
        assert len(body["keys"]) == 1
        assert "token" not in body["keys"][0]  # token never returned in list

    def test_delete_key_hard_delete(self):
        user = _make_user()
        mock_svc = AsyncMock()
        mock_svc.revoke = AsyncMock(return_value=True)

        application = _build_test_app(
            {require_auth: lambda: user, get_api_key_service: lambda: mock_svc}
        )
        key_id = str(ObjectId())
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.delete(f"/api/v1/keys/{key_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["action"] == "deleted"
        assert body["success"] is True
        mock_svc.revoke.assert_called_once_with(
            user.user_id, ObjectId(key_id), hard_delete=True
        )

    def test_delete_key_soft_revoke(self):
        user = _make_user()
        mock_svc = AsyncMock()
        mock_svc.revoke = AsyncMock(return_value=True)

        application = _build_test_app(
            {require_auth: lambda: user, get_api_key_service: lambda: mock_svc}
        )
        key_id = str(ObjectId())
        with TestClient(application, raise_server_exceptions=True) as client:
            resp = client.delete(f"/api/v1/keys/{key_id}?revoke=true")

        assert resp.status_code == 200
        body = resp.json()
        assert body["action"] == "revoked"
        mock_svc.revoke.assert_called_once_with(
            user.user_id, ObjectId(key_id), hard_delete=False
        )

    def test_delete_key_not_found_returns_404(self):
        user = _make_user()
        mock_svc = AsyncMock()
        mock_svc.revoke = AsyncMock(return_value=False)

        application = _build_test_app(
            {require_auth: lambda: user, get_api_key_service: lambda: mock_svc}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.delete(f"/api/v1/keys/{ObjectId()}")

        assert resp.status_code == 404

    def test_delete_key_invalid_id_returns_404(self):
        """Non-ObjectId key_id is treated as not-found (no information leak)."""
        user = _make_user()

        application = _build_test_app(
            {require_auth: lambda: user, get_api_key_service: lambda: AsyncMock()}
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            resp = client.delete("/api/v1/keys/not-an-objectid")

        assert resp.status_code == 404
