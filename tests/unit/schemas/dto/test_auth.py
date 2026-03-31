"""Unit tests for auth request and response DTOs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.dto.requests.auth import (
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from schemas.dto.responses.auth import (
    AuthProviderInfo,
    UserProfileResponse,
)

# ── Auth request DTOs ──────────────────────────────────────────────────────────


class TestLoginRequest:
    def test_valid(self):
        req = LoginRequest.model_validate(
            {"email": "u@example.com", "password": "Pass123!x"}
        )
        assert req.email == "u@example.com"

    @pytest.mark.parametrize(
        "payload",
        [{"password": "Pass123!x"}, {"email": "u@example.com"}, {}],
        ids=["missing_email", "missing_password", "missing_both"],
    )
    def test_missing_required_fields_rejected(self, payload):
        with pytest.raises(ValidationError):
            LoginRequest.model_validate(payload)


class TestRegisterRequest:
    def test_valid_minimal(self):
        req = RegisterRequest.model_validate(
            {"email": "u@example.com", "password": "Pass123!x"}
        )
        assert req.user_name is None

    def test_optional_user_name(self):
        req = RegisterRequest.model_validate(
            {"email": "u@example.com", "password": "Pass123!x", "user_name": "Alice"}
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
            {"email": "u@example.com", "code": "123456", "password": "NewPass1!"}
        )
        assert req.code == "123456"

    def test_all_fields_required(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest.model_validate({"email": "u@example.com"})


# ── Auth response DTOs ─────────────────────────────────────────────────────────


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
