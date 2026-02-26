"""Unit tests for request and response DTOs (Phase 3)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from schemas.dto.requests.api_key import CreateApiKeyRequest
from schemas.dto.requests.auth import (
    LoginRequest,
    RegisterRequest,
    RequestPasswordResetRequest,
    ResetPasswordRequest,
    SetPasswordRequest,
    VerifyEmailRequest,
)
from schemas.dto.requests.stats import ExportQuery, StatsQuery
from schemas.dto.requests.url import (
    CreateUrlRequest,
    ListUrlsQuery,
    UpdateUrlRequest,
    UrlFilter,
)
from schemas.dto.responses.api_key import (
    ApiKeyActionResponse,
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    ApiKeysListResponse,
)
from schemas.dto.responses.auth import (
    AuthProviderInfo,
    LoginResponse,
    RegisterResponse,
    UserProfileResponse,
)
from schemas.dto.responses.common import ErrorResponse, HealthResponse, MessageResponse
from schemas.dto.responses.stats import (
    ComputedMetrics,
    StatsSummary,
    StatsResponse,
    StatsTimeRange,
)
from schemas.dto.responses.url import (
    UpdateUrlResponse,
    UrlListItem,
    UrlListResponse,
    UrlResponse,
)


# ── CreateUrlRequest ───────────────────────────────────────────────────────────


class TestCreateUrlRequest:
    def test_accepts_long_url(self):
        req = CreateUrlRequest.model_validate({"long_url": "https://example.com"})
        assert req.long_url == "https://example.com"

    def test_accepts_url_alias(self):
        """``url`` field is accepted as an alias for ``long_url``."""
        req = CreateUrlRequest.model_validate({"url": "https://example.com"})
        assert req.long_url == "https://example.com"

    def test_requires_long_url(self):
        with pytest.raises(ValidationError):
            CreateUrlRequest.model_validate({"alias": "abc"})

    def test_max_clicks_must_be_positive(self):
        with pytest.raises(ValidationError):
            CreateUrlRequest.model_validate(
                {"long_url": "https://example.com", "max_clicks": 0}
            )

    def test_max_clicks_negative_rejected(self):
        with pytest.raises(ValidationError):
            CreateUrlRequest.model_validate(
                {"long_url": "https://example.com", "max_clicks": -5}
            )

    def test_max_clicks_positive_accepted(self):
        req = CreateUrlRequest.model_validate(
            {"long_url": "https://example.com", "max_clicks": 10}
        )
        assert req.max_clicks == 10

    def test_optional_fields_default_none(self):
        req = CreateUrlRequest.model_validate({"long_url": "https://example.com"})
        assert req.alias is None
        assert req.password is None
        assert req.block_bots is None
        assert req.max_clicks is None
        assert req.expire_after is None
        assert req.private_stats is None

    def test_all_optional_fields(self):
        req = CreateUrlRequest.model_validate(
            {
                "long_url": "https://example.com",
                "alias": "mylink",
                "password": "p@ssw0rd",
                "block_bots": True,
                "max_clicks": 100,
                "expire_after": 9999999999,
                "private_stats": False,
            }
        )
        assert req.alias == "mylink"
        assert req.block_bots is True
        assert req.max_clicks == 100


# ── UpdateUrlRequest ───────────────────────────────────────────────────────────


class TestUpdateUrlRequest:
    def test_all_fields_optional(self):
        req = UpdateUrlRequest.model_validate({})
        assert req.long_url is None
        assert req.alias is None
        assert req.status is None

    @pytest.mark.parametrize(
        "status",
        ["ACTIVE", "INACTIVE"],
        ids=["active", "inactive"],
    )
    def test_accepts_valid_status(self, status):
        assert UpdateUrlRequest.model_validate({"status": status}).status == status

    @pytest.mark.parametrize(
        "status",
        ["DELETED", "UNKNOWN", "invalid"],
        ids=["deleted", "unknown", "invalid"],
    )
    def test_rejects_invalid_status(self, status):
        with pytest.raises(ValidationError):
            UpdateUrlRequest.model_validate({"status": status})

    def test_url_alias_maps_to_long_url(self):
        req = UpdateUrlRequest.model_validate({"url": "https://new.example.com"})
        assert req.long_url == "https://new.example.com"

    def test_max_clicks_zero_allowed(self):
        """0 is allowed in update to signal removing the limit."""
        assert UpdateUrlRequest.model_validate({"max_clicks": 0}).max_clicks == 0

    def test_max_clicks_negative_rejected(self):
        with pytest.raises(ValidationError):
            UpdateUrlRequest.model_validate({"max_clicks": -1})


# ── ListUrlsQuery ──────────────────────────────────────────────────────────────


class TestListUrlsQuery:
    def test_defaults(self):
        q = ListUrlsQuery.model_validate({})
        assert q.page == 1
        assert q.page_size == 20
        assert q.sort_by == "created_at"
        assert q.sort_order == "descending"

    def test_camelcase_aliases(self):
        q = ListUrlsQuery.model_validate(
            {"pageSize": 50, "sortBy": "total_clicks", "sortOrder": "ascending"}
        )
        assert q.page_size == 50
        assert q.sort_by == "total_clicks"

    def test_page_must_be_ge_1(self):
        with pytest.raises(ValidationError):
            ListUrlsQuery.model_validate({"page": 0})

    def test_page_size_max_100(self):
        with pytest.raises(ValidationError):
            ListUrlsQuery.model_validate({"pageSize": 101})

    def test_invalid_sort_by_falls_back_to_created_at(self):
        assert (
            ListUrlsQuery.model_validate({"sortBy": "invalid_field"}).sort_by
            == "created_at"
        )

    def test_valid_filter_json_parsed(self):
        filter_json = json.dumps({"status": "ACTIVE", "passwordSet": True})
        q = ListUrlsQuery.model_validate({"filter": filter_json})
        assert q.parsed_filter.status == "ACTIVE"
        assert q.parsed_filter.password_set is True

    def test_invalid_filter_json_raises(self):
        with pytest.raises(ValidationError):
            ListUrlsQuery.model_validate({"filter": "{not valid json"})

    def test_filter_non_object_rejected(self):
        with pytest.raises(ValidationError):
            ListUrlsQuery.model_validate({"filter": "[1, 2, 3]"})

    def test_filter_by_alias_also_works(self):
        filter_json = json.dumps({"search": "example"})
        q = ListUrlsQuery.model_validate({"filterBy": filter_json})
        assert q.parsed_filter is not None
        assert q.parsed_filter.search == "example"

    def test_no_filter_leaves_parsed_filter_none(self):
        assert ListUrlsQuery.model_validate({}).parsed_filter is None


# ── Auth request DTOs ──────────────────────────────────────────────────────────


class TestLoginRequest:
    def test_valid(self):
        req = LoginRequest.model_validate(
            {"email": "u@example.com", "password": "pass"}
        )
        assert req.email == "u@example.com"

    @pytest.mark.parametrize(
        "payload",
        [{"password": "pass"}, {"email": "u@example.com"}, {}],
        ids=["missing_email", "missing_password", "missing_both"],
    )
    def test_missing_required_fields_rejected(self, payload):
        with pytest.raises(ValidationError):
            LoginRequest.model_validate(payload)


class TestRegisterRequest:
    def test_valid_minimal(self):
        req = RegisterRequest.model_validate(
            {"email": "u@example.com", "password": "pass"}
        )
        assert req.user_name is None

    def test_optional_user_name(self):
        req = RegisterRequest.model_validate(
            {"email": "u@example.com", "password": "pass", "user_name": "Alice"}
        )
        assert req.user_name == "Alice"


class TestVerifyEmailRequest:
    def test_valid(self):
        assert VerifyEmailRequest.model_validate({"code": "123456"}).code == "123456"

    def test_requires_code(self):
        with pytest.raises(ValidationError):
            VerifyEmailRequest.model_validate({})


class TestResetPasswordRequest:
    def test_valid(self):
        req = ResetPasswordRequest.model_validate(
            {"email": "u@example.com", "code": "123456", "password": "newpass"}
        )
        assert req.code == "123456"

    def test_all_fields_required(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest.model_validate({"email": "u@example.com"})


# ── StatsQuery ─────────────────────────────────────────────────────────────────


class TestStatsQuery:
    def test_defaults(self):
        q = StatsQuery.model_validate({})
        assert q.scope == "all"
        assert q.parsed_group_by == ["time"]
        assert q.parsed_metrics == ["clicks", "unique_clicks"]
        assert q.timezone == "UTC"

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValidationError):
            StatsQuery.model_validate({"scope": "invalid"})

    def test_comma_separated_group_by(self):
        q = StatsQuery.model_validate({"group_by": "time,browser,os"})
        assert "time" in q.parsed_group_by
        assert "browser" in q.parsed_group_by

    def test_invalid_group_by_rejected(self):
        with pytest.raises(ValidationError):
            StatsQuery.model_validate({"group_by": "time,device"})

    def test_comma_separated_metrics(self):
        assert StatsQuery.model_validate(
            {"metrics": "unique_clicks"}
        ).parsed_metrics == ["unique_clicks"]

    def test_invalid_metric_rejected(self):
        with pytest.raises(ValidationError):
            StatsQuery.model_validate({"metrics": "clicks,pageviews"})

    def test_filters_json_parsed(self):
        q = StatsQuery.model_validate(
            {"filters": json.dumps({"browser": "Chrome,Firefox"})}
        )
        assert "Chrome" in q.parsed_filters["browser"]

    def test_invalid_filters_json_rejected(self):
        with pytest.raises(ValidationError):
            StatsQuery.model_validate({"filters": "{bad json"})

    def test_individual_filter_params_parsed(self):
        q = StatsQuery.model_validate({"browser": "Chrome", "country": "US,DE"})
        assert q.parsed_filters.get("browser") == ["Chrome"]
        assert "DE" in q.parsed_filters.get("country", [])


# ── ExportQuery ────────────────────────────────────────────────────────────────


class TestExportQuery:
    @pytest.mark.parametrize("fmt", ["csv", "xlsx", "json", "xml"])
    def test_valid_format(self, fmt):
        assert ExportQuery.model_validate({"format": fmt}).format == fmt

    def test_missing_format_rejected(self):
        with pytest.raises(ValidationError):
            ExportQuery.model_validate({})

    @pytest.mark.parametrize("fmt", ["pdf", "txt", "docx", ""])
    def test_invalid_format_rejected(self, fmt):
        with pytest.raises(ValidationError):
            ExportQuery.model_validate({"format": fmt})

    def test_inherits_stats_fields(self):
        q = ExportQuery.model_validate({"format": "xlsx", "scope": "all"})
        assert q.scope == "all"


# ── CreateApiKeyRequest ────────────────────────────────────────────────────────


class TestCreateApiKeyRequest:
    def test_valid(self):
        req = CreateApiKeyRequest.model_validate(
            {"name": "My Key", "scopes": ["shorten:create"]}
        )
        assert req.name == "My Key"
        assert req.description is None
        assert req.expires_at is None

    @pytest.mark.parametrize(
        "payload",
        [
            {"name": "  ", "scopes": ["shorten:create"]},  # blank name
            {"name": "Key", "scopes": []},  # empty scopes
            {"name": "Key", "scopes": ["unknown:scope"]},  # invalid scope
        ],
        ids=["blank_name", "empty_scopes", "invalid_scope"],
    )
    def test_invalid_input_rejected(self, payload):
        with pytest.raises(ValidationError):
            CreateApiKeyRequest.model_validate(payload)

    def test_valid_all_scopes(self):
        req = CreateApiKeyRequest.model_validate(
            {
                "name": "Admin Key",
                "scopes": [
                    "shorten:create",
                    "urls:manage",
                    "urls:read",
                    "stats:read",
                    "admin:all",
                ],
            }
        )
        assert len(req.scopes) == 5

    def test_optional_fields(self):
        req = CreateApiKeyRequest.model_validate(
            {
                "name": "Key",
                "scopes": ["shorten:create"],
                "description": "test key",
                "expires_at": 9999999999,
            }
        )
        assert req.description == "test key"
        assert req.expires_at == 9999999999


# ── Response DTO serialization shapes ─────────────────────────────────────────


class TestErrorResponse:
    def test_minimal(self):
        d = ErrorResponse(error="not found", error_code="not_found").model_dump(
            exclude_none=True
        )
        assert d == {"error": "not found", "error_code": "not_found"}

    def test_with_field_and_details(self):
        r = ErrorResponse(
            error="bad input",
            error_code="validation_error",
            field="email",
            details={"hint": "must be valid email"},
        )
        d = r.model_dump()
        assert d["field"] == "email"
        assert d["details"] == {"hint": "must be valid email"}

    def test_without_optional_fields(self):
        d = ErrorResponse(error="fail", error_code="err").model_dump()
        assert d["field"] is None
        assert d["details"] is None


class TestUrlResponse:
    def test_serialization(self):
        r = UrlResponse(
            alias="abc1234",
            short_url="https://spoo.me/abc1234",
            long_url="https://example.com",
            owner_id="507f1f77bcf86cd799439011",
            created_at=1704067200,
            status="ACTIVE",
            private_stats=True,
        )
        d = r.model_dump()
        assert d["alias"] == "abc1234"
        assert d["created_at"] == 1704067200
        assert d["status"] == "ACTIVE"

    def test_owner_id_optional(self):
        r = UrlResponse(
            alias="abc1234",
            short_url="https://spoo.me/abc1234",
            long_url="https://example.com",
            created_at=1704067200,
            status="ACTIVE",
        )
        assert r.owner_id is None


class TestUrlListResponse:
    def test_camelcase_keys_in_output(self):
        r = UrlListResponse(
            items=[],
            page=1,
            pageSize=20,
            total=0,
            hasNext=False,
            sortBy="created_at",
            sortOrder="descending",
        )
        d = r.model_dump()
        assert "pageSize" in d
        assert "hasNext" in d
        assert "sortBy" in d
        assert "sortOrder" in d
        assert d["pageSize"] == 20
        assert d["hasNext"] is False


class TestApiKeyCreatedResponse:
    def test_has_token_field(self):
        r = ApiKeyCreatedResponse(
            id="507f1f77bcf86cd799439011",
            name="My Key",
            scopes=["shorten:create"],
            created_at=1704067200,
            revoked=False,
            token_prefix="AbCdEfGh",
            token="spoo_AbCdEfGhIjKlMnOpQrStUvWxYz",
        )
        d = r.model_dump()
        assert d["token"] == "spoo_AbCdEfGhIjKlMnOpQrStUvWxYz"
        assert d["token_prefix"] == "AbCdEfGh"

    def test_expires_at_null(self):
        r = ApiKeyCreatedResponse(
            id="507f1f77bcf86cd799439011",
            name="Key",
            scopes=["shorten:create"],
            created_at=1704067200,
            revoked=False,
            token_prefix="AbCdEfGh",
            token="spoo_abc",
        )
        assert r.expires_at is None


class TestHealthResponse:
    def test_serialization(self):
        r = HealthResponse(status="healthy", checks={"mongodb": "ok", "redis": "ok"})
        d = r.model_dump()
        assert d["status"] == "healthy"
        assert d["checks"]["mongodb"] == "ok"


class TestUserProfileResponse:
    def test_minimal(self):
        r = UserProfileResponse(
            id="507f1f77bcf86cd799439011",
            email="u@example.com",
            email_verified=False,
            plan="free",
            password_set=False,
            auth_providers=[],
        )
        d = r.model_dump()
        assert d["id"] == "507f1f77bcf86cd799439011"
        assert d["email_verified"] is False

    def test_pfp_none_excluded(self):
        r = UserProfileResponse(
            id="507f1f77bcf86cd799439011",
            email="u@example.com",
            email_verified=True,
            plan="free",
            password_set=True,
            auth_providers=[],
            pfp=None,
        )
        assert "pfp" not in r.model_dump(exclude_none=True)

    def test_with_auth_provider(self):
        r = UserProfileResponse(
            id="507f1f77bcf86cd799439011",
            email="u@example.com",
            email_verified=True,
            plan="free",
            password_set=False,
            auth_providers=[
                AuthProviderInfo(
                    provider="google",
                    email="u@example.com",
                    linked_at="2024-01-01T00:00:00Z",
                )
            ],
        )
        assert r.auth_providers[0].provider == "google"


class TestStatsResponse:
    def test_serialization(self):
        r = StatsResponse(
            scope="all",
            filters={},
            group_by=["time"],
            timezone="UTC",
            time_range=StatsTimeRange(
                start_date="2024-01-01T00:00:00Z",
                end_date="2024-01-08T00:00:00Z",
            ),
            summary=StatsSummary(
                total_clicks=10,
                unique_clicks=8,
                first_click="2024-01-01T10:00:00Z",
                last_click="2024-01-07T10:00:00Z",
                avg_redirection_time=42.5,
            ),
            metrics={"clicks_by_time": [{"date": "2024-01-01", "clicks": 5}]},
            api_version="v1",
        )
        d = r.model_dump()
        assert d["scope"] == "all"
        assert d["summary"]["total_clicks"] == 10
        assert "clicks_by_time" in d["metrics"]
