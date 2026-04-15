"""Unit tests for Phase 8 — OAuthService."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from errors import ConflictError, NotFoundError, ValidationError
from schemas.models.user import ProviderInfo, UserDoc
from schemas.results import AuthResult

# ── Constants ────────────────────────────────────────────────────────────────

USER_OID = ObjectId("aaaaaaaaaaaaaaaaaaaaaaaa")
OTHER_OID = ObjectId("bbbbbbbbbbbbbbbbbbbbbbbb")


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


def make_user_doc(
    oid=USER_OID,
    email="test@example.com",
    email_verified=True,
    password_set=False,
    auth_providers=None,
):
    doc: dict[str, Any] = {
        "_id": oid,
        "email": email,
        "email_verified": email_verified,
        "password_hash": None,
        "password_set": password_set,
        "user_name": "Test User",
        "pfp": None,
        "auth_providers": auth_providers or [],
        "plan": "free",
        "status": "ACTIVE",
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }
    return UserDoc.from_mongo(doc)


def make_provider_info(
    provider_user_id="google123",
    email="test@example.com",
    email_verified=True,
    name="Test User",
    picture="https://pic.url",
) -> ProviderInfo:
    return ProviderInfo(
        provider_user_id=provider_user_id,
        email=email,
        email_verified=email_verified,
        name=name,
        picture=picture,
        given_name="Test",
        family_name="User",
    )


def make_token_factory():
    """Create a real TokenFactory with working token generation."""
    from services.token_factory import TokenFactory

    return TokenFactory(make_jwt_settings())


def make_oauth_service(token_factory=None):
    from services.oauth_service import OAuthService

    if token_factory is None:
        token_factory = make_token_factory()
    return OAuthService(
        user_repo=AsyncMock(),
        token_factory=token_factory,
        email=AsyncMock(),
    )


# ── handle_callback: existing OAuth user (flow 2) ────────────────────────────


class TestHandleCallbackExistingOAuthUser:
    @pytest.mark.asyncio
    async def test_existing_oauth_user_login_success(self):
        svc = make_oauth_service()
        user = make_user_doc()
        # No user by provider_user_id at first means provider user IS found
        svc._user_repo.find_by_oauth_provider.return_value = user

        result = await svc.handle_callback(
            provider_key="google",
            provider_info=make_provider_info(),
            action="login",
            state_data={"action": "login"},
        )
        assert isinstance(result, AuthResult)
        assert result.user is user
        assert isinstance(result.access_token, str)
        assert isinstance(result.refresh_token, str)
        svc._user_repo.update.assert_awaited()  # last_login_at updated

    @pytest.mark.asyncio
    async def test_existing_oauth_user_tokens_use_provider_as_amr(self):
        import jwt as pyjwt

        svc = make_oauth_service()
        user = make_user_doc()
        svc._user_repo.find_by_oauth_provider.return_value = user
        settings = make_jwt_settings()

        result = await svc.handle_callback(
            provider_key="github",
            provider_info=make_provider_info(),
            action="login",
            state_data={"action": "login"},
        )
        payload = pyjwt.decode(
            result.access_token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        assert payload["amr"] == ["github"]


# ── handle_callback: new user (flow 4) ───────────────────────────────────────


class TestHandleCallbackNewUser:
    @pytest.mark.asyncio
    async def test_new_user_creation_success(self):
        svc = make_oauth_service()
        new_user = make_user_doc()
        svc._user_repo.find_by_oauth_provider.return_value = None
        svc._user_repo.find_by_email.return_value = None
        svc._user_repo.create.return_value = USER_OID
        svc._user_repo.find_by_id.return_value = new_user
        svc._email.send_welcome_email.return_value = True

        result = await svc.handle_callback(
            provider_key="google",
            provider_info=make_provider_info(),
            action="login",
            state_data={"action": "login"},
        )
        assert result.user is new_user
        svc._user_repo.create.assert_awaited_once()
        svc._email.send_welcome_email.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_new_user_welcome_email_failure_is_non_fatal(self):
        """User creation succeeds even if welcome email fails."""
        svc = make_oauth_service()
        new_user = make_user_doc()
        svc._user_repo.find_by_oauth_provider.return_value = None
        svc._user_repo.find_by_email.return_value = None
        svc._user_repo.create.return_value = USER_OID
        svc._user_repo.find_by_id.return_value = new_user
        svc._email.send_welcome_email.side_effect = Exception("email down")

        result = await svc.handle_callback(
            provider_key="google",
            provider_info=make_provider_info(),
            action="login",
            state_data={"action": "login"},
        )
        assert result.user is new_user  # did not raise


# ── handle_callback: email collision + auto-link (flow 3) ────────────────────


class TestHandleCallbackAutoLink:
    @pytest.mark.asyncio
    async def test_auto_link_when_provider_email_verified(self):
        svc = make_oauth_service()
        existing_user = make_user_doc(email="test@example.com")
        updated_user = make_user_doc(email="test@example.com")
        svc._user_repo.find_by_oauth_provider.return_value = None
        svc._user_repo.find_by_email.return_value = existing_user
        svc._user_repo.update.return_value = True
        svc._user_repo.find_by_id.return_value = updated_user

        provider_info = make_provider_info(
            provider_user_id="google999",
            email="test@example.com",
            email_verified=True,  # required for auto-link
        )
        result = await svc.handle_callback(
            provider_key="google",
            provider_info=provider_info,
            action="login",
            state_data={"action": "login"},
        )
        assert result.user is updated_user
        # update called for linking + last_login
        assert svc._user_repo.update.await_count >= 1

    @pytest.mark.asyncio
    async def test_email_collision_rejected_when_provider_email_unverified(self):
        svc = make_oauth_service()
        existing_user = make_user_doc(email="test@example.com")
        svc._user_repo.find_by_oauth_provider.return_value = None
        svc._user_repo.find_by_email.return_value = existing_user

        provider_info = make_provider_info(
            provider_user_id="google999",
            email="test@example.com",
            email_verified=False,  # not verified → cannot auto-link
        )
        with pytest.raises(ConflictError, match="email already exists"):
            await svc.handle_callback(
                provider_key="google",
                provider_info=provider_info,
                action="login",
                state_data={"action": "login"},
            )

    @pytest.mark.asyncio
    async def test_email_collision_rejected_when_already_linked_to_provider(self):
        """Cannot auto-link if provider already linked to the email-matched user."""
        svc = make_oauth_service()
        existing_user = make_user_doc(
            email="test@example.com",
            auth_providers=[
                {
                    "provider": "google",
                    "provider_user_id": "other_google_id",
                    "email": "test@example.com",
                    "email_verified": True,
                    "profile": {"name": "Test", "picture": ""},
                    "linked_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
                }
            ],
        )
        svc._user_repo.find_by_oauth_provider.return_value = None
        svc._user_repo.find_by_email.return_value = existing_user

        provider_info = make_provider_info(
            provider_user_id="yet_another_google_id",
            email="test@example.com",
            email_verified=True,
        )
        with pytest.raises(ConflictError, match="email already exists"):
            await svc.handle_callback(
                provider_key="google",
                provider_info=provider_info,
                action="login",
                state_data={"action": "login"},
            )


# ── handle_callback: account linking (flow 1) ────────────────────────────────


class TestHandleCallbackLink:
    @pytest.mark.asyncio
    async def test_link_flow_success(self):
        svc = make_oauth_service()
        current_user = make_user_doc(oid=USER_OID, email="test@example.com")
        updated_user = make_user_doc(oid=USER_OID, email="test@example.com")
        svc._user_repo.find_by_id.return_value = current_user
        svc._user_repo.find_by_oauth_provider.return_value = None
        svc._user_repo.update.return_value = True
        # Second find_by_id call after linking returns updated_user
        svc._user_repo.find_by_id.side_effect = [current_user, updated_user]

        result = await svc.handle_callback(
            provider_key="google",
            provider_info=make_provider_info(email="test@example.com"),
            action="link",
            state_data={"action": "link", "user_id": str(USER_OID)},
        )
        assert result.user is updated_user

    @pytest.mark.asyncio
    async def test_link_flow_missing_user_id_raises(self):
        svc = make_oauth_service()

        with pytest.raises(ValidationError, match="invalid linking request"):
            await svc.handle_callback(
                provider_key="google",
                provider_info=make_provider_info(),
                action="link",
                state_data={"action": "link"},  # no user_id
            )

    @pytest.mark.asyncio
    async def test_link_flow_user_not_found_raises(self):
        svc = make_oauth_service()
        svc._user_repo.find_by_id.return_value = None

        with pytest.raises(NotFoundError, match="user not found"):
            await svc.handle_callback(
                provider_key="google",
                provider_info=make_provider_info(),
                action="link",
                state_data={"action": "link", "user_id": str(USER_OID)},
            )

    @pytest.mark.asyncio
    async def test_link_flow_provider_already_linked_raises(self):
        svc = make_oauth_service()
        current_user = make_user_doc(
            email="test@example.com",
            auth_providers=[
                {
                    "provider": "google",
                    "provider_user_id": "existing_google_id",
                    "email": "test@example.com",
                    "email_verified": True,
                    "profile": {"name": "Test", "picture": ""},
                    "linked_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
                }
            ],
        )
        svc._user_repo.find_by_id.return_value = current_user

        with pytest.raises(ConflictError, match="Google account already linked"):
            await svc.handle_callback(
                provider_key="google",
                provider_info=make_provider_info(email="test@example.com"),
                action="link",
                state_data={"action": "link", "user_id": str(USER_OID)},
            )

    @pytest.mark.asyncio
    async def test_link_flow_provider_owned_by_other_user_raises(self):
        """provider_user_id already linked to a different account."""
        svc = make_oauth_service()
        current_user = make_user_doc(oid=USER_OID, email="test@example.com")
        other_user = make_user_doc(oid=OTHER_OID, email="other@example.com")
        svc._user_repo.find_by_id.return_value = current_user
        svc._user_repo.find_by_oauth_provider.return_value = (
            other_user  # different user
        )

        with pytest.raises(ConflictError, match="already linked to another user"):
            await svc.handle_callback(
                provider_key="google",
                provider_info=make_provider_info(email="test@example.com"),
                action="link",
                state_data={"action": "link", "user_id": str(USER_OID)},
            )

    @pytest.mark.asyncio
    async def test_link_flow_email_mismatch_raises(self):
        svc = make_oauth_service()
        current_user = make_user_doc(oid=USER_OID, email="test@example.com")
        svc._user_repo.find_by_id.return_value = current_user
        svc._user_repo.find_by_oauth_provider.return_value = None

        # Provider email differs from user's account email
        provider_info = make_provider_info(email="different@gmail.com")
        with pytest.raises(ValidationError, match="email mismatch"):
            await svc.handle_callback(
                provider_key="google",
                provider_info=provider_info,
                action="link",
                state_data={"action": "link", "user_id": str(USER_OID)},
            )


# ── unlink_provider tests ─────────────────────────────────────────────────────


class TestUnlinkProvider:
    @pytest.mark.asyncio
    async def test_unlink_success(self):
        svc = make_oauth_service()
        user = make_user_doc(
            password_set=True,
            auth_providers=[
                {
                    "provider": "google",
                    "provider_user_id": "g123",
                    "email": "test@example.com",
                    "email_verified": True,
                    "profile": {"name": "T", "picture": ""},
                    "linked_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
                }
            ],
        )
        svc._user_repo.find_by_id.return_value = user
        svc._user_repo.update.return_value = True

        await svc.unlink_provider(str(USER_OID), "google")
        svc._user_repo.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unlink_refuses_to_remove_last_auth_method_without_password(self):
        """Cannot remove last provider when no password is set."""
        svc = make_oauth_service()
        user = make_user_doc(
            password_set=False,  # no password
            auth_providers=[
                {
                    "provider": "google",
                    "provider_user_id": "g123",
                    "email": "test@example.com",
                    "email_verified": True,
                    "profile": {"name": "T", "picture": ""},
                    "linked_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
                }
            ],
        )
        svc._user_repo.find_by_id.return_value = user

        with pytest.raises(
            ValidationError, match="cannot unlink last authentication method"
        ):
            await svc.unlink_provider(str(USER_OID), "google")

    @pytest.mark.asyncio
    async def test_unlink_user_not_found_raises(self):
        svc = make_oauth_service()
        svc._user_repo.find_by_id.return_value = None

        with pytest.raises(NotFoundError, match="user not found"):
            await svc.unlink_provider(str(USER_OID), "google")

    @pytest.mark.asyncio
    async def test_unlink_allows_removal_when_password_is_set(self):
        """Can remove last provider when password IS set."""
        svc = make_oauth_service()
        user = make_user_doc(
            password_set=True,  # has password → safe to remove
            auth_providers=[
                {
                    "provider": "google",
                    "provider_user_id": "g123",
                    "email": "test@example.com",
                    "email_verified": True,
                    "profile": {"name": "T", "picture": ""},
                    "linked_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
                }
            ],
        )
        svc._user_repo.find_by_id.return_value = user
        svc._user_repo.update.return_value = True

        # Should not raise
        await svc.unlink_provider(str(USER_OID), "google")


# ── list_providers tests ──────────────────────────────────────────────────────


class TestListProviders:
    @pytest.mark.asyncio
    async def test_list_providers_success(self):
        svc = make_oauth_service()
        user = make_user_doc(
            password_set=True,
            auth_providers=[
                {
                    "provider": "google",
                    "provider_user_id": "g123",
                    "email": "test@gmail.com",
                    "email_verified": True,
                    "profile": {"name": "Test User", "picture": "https://pic.url"},
                    "linked_at": datetime(2024, 6, 1, tzinfo=timezone.utc),
                }
            ],
        )
        svc._user_repo.find_by_id.return_value = user

        providers, password_set = await svc.list_providers(str(USER_OID))
        assert len(providers) == 1
        assert providers[0].provider == "google"
        assert providers[0].email == "test@gmail.com"
        assert providers[0].email_verified is True
        assert password_set is True

    @pytest.mark.asyncio
    async def test_list_providers_empty(self):
        svc = make_oauth_service()
        user = make_user_doc(password_set=False, auth_providers=[])
        svc._user_repo.find_by_id.return_value = user

        providers, password_set = await svc.list_providers(str(USER_OID))
        assert providers == []
        assert password_set is False

    @pytest.mark.asyncio
    async def test_list_providers_user_not_found_raises(self):
        svc = make_oauth_service()
        svc._user_repo.find_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await svc.list_providers(str(USER_OID))
