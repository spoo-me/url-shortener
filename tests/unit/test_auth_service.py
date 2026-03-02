"""Unit tests for Phase 8 — AuthService."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import AsyncMock
from bson import ObjectId

import jwt as pyjwt
import pytest

from schemas.models.user import UserDoc

# ── Constants ────────────────────────────────────────────────────────────────

USER_OID = ObjectId("aaaaaaaaaaaaaaaaaaaaaaaa")


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_jwt_settings():
    from config import JWTSettings
    return JWTSettings(
        jwt_issuer="spoo.me",
        jwt_audience="spoo.me.api",
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=2592000,
        jwt_secret="test-secret-key-at-least-32-chars!!",
        jwt_private_key="",
        jwt_public_key="",
    )


def make_user_doc(email_verified=True, password_set=False, password_hash=None, auth_providers=None):
    doc = {
        "_id": USER_OID,
        "email": "test@example.com",
        "email_verified": email_verified,
        "password_hash": password_hash,
        "password_set": password_set,
        "user_name": "Test User",
        "pfp": None,
        "auth_providers": auth_providers or [],
        "plan": "free",
        "signup_ip": "1.2.3.4",
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "status": "ACTIVE",
    }
    return UserDoc.from_mongo(doc)


def make_auth_service():
    from services.auth_service import AuthService
    return AuthService(
        user_repo=AsyncMock(),
        token_repo=AsyncMock(),
        email=AsyncMock(),
        settings=make_jwt_settings(),
    )


# ── JWT tests ─────────────────────────────────────────────────────────────────

class TestJWTHelpers:
    def test_generate_access_token_returns_string(self):
        svc = make_auth_service()
        token = svc._generate_access_token(make_user_doc(), amr="pwd")
        assert isinstance(token, str)

    def test_access_token_has_correct_claims(self):
        svc = make_auth_service()
        settings = make_jwt_settings()
        token = svc._generate_access_token(make_user_doc(email_verified=True), amr="pwd")
        payload = pyjwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        assert payload["sub"] == str(USER_OID)
        assert payload["iss"] == "spoo.me"
        assert payload["aud"] == "spoo.me.api"
        assert payload["amr"] == ["pwd"]
        assert payload["email_verified"] is True
        assert "type" not in payload
        assert payload["exp"] - payload["iat"] == 900

    def test_refresh_token_has_type_field(self):
        svc = make_auth_service()
        settings = make_jwt_settings()
        token = svc._generate_refresh_token(make_user_doc(), amr="google")
        payload = pyjwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        assert payload["type"] == "refresh"
        assert payload["amr"] == ["google"]
        assert payload["exp"] - payload["iat"] == 2592000

    def test_verify_token_returns_payload(self):
        svc = make_auth_service()
        token = svc._generate_access_token(make_user_doc(), amr="pwd")
        payload = svc._verify_token(token, token_type="access")
        assert payload["sub"] == str(USER_OID)

    def test_verify_refresh_token_requires_type_field(self):
        svc = make_auth_service()
        refresh = svc._generate_refresh_token(make_user_doc(), amr="pwd")
        access = svc._generate_access_token(make_user_doc(), amr="pwd")
        # refresh passes as "refresh"
        assert svc._verify_token(refresh, token_type="refresh")["type"] == "refresh"
        # access token fails as "refresh" (no type field)
        from errors import AuthenticationError
        with pytest.raises(AuthenticationError):
            svc._verify_token(access, token_type="refresh")

    def test_verify_invalid_token_raises_auth_error(self):
        svc = make_auth_service()
        from errors import AuthenticationError
        with pytest.raises(AuthenticationError):
            svc._verify_token("not.a.valid.token", token_type="access")
