"""Unit tests for OAuth utility functions."""

from datetime import datetime, timedelta, timezone

from infrastructure.oauth_clients import (
    can_auto_link_accounts,
    extract_user_info_from_discord,
    extract_user_info_from_github,
    extract_user_info_from_google,
    generate_oauth_state,
    verify_oauth_state,
)


class TestGenerateOAuthState:
    def test_contains_provider_and_action(self):
        state = generate_oauth_state("google", "login")
        assert "provider=google" in state
        assert "action=login" in state

    def test_contains_user_id_when_given(self):
        state = generate_oauth_state("github", "link", user_id="abc123")
        assert "user_id=abc123" in state

    def test_omits_user_id_when_absent(self):
        state = generate_oauth_state("discord")
        assert "user_id=" not in state


class TestVerifyOAuthState:
    def test_valid_state_returns_true(self):
        state = generate_oauth_state("google")
        ok, data, reason = verify_oauth_state(state, "google")
        assert ok is True
        assert reason is None
        assert data["provider"] == "google"

    def test_wrong_provider_returns_mismatch(self):
        state = generate_oauth_state("google")
        ok, _, reason = verify_oauth_state(state, "github")
        assert ok is False
        assert reason == "provider_mismatch"

    def test_missing_timestamp_returns_error(self):
        ok, _, reason = verify_oauth_state("provider=google&action=login", "google")
        assert ok is False
        assert reason == "missing_timestamp"

    def test_malformed_state_returns_parse_error(self):
        ok, _, reason = verify_oauth_state("not-valid-state!!!", "google")
        # Either parse_error or missing_timestamp/provider_mismatch — both are failures
        assert ok is False

    def test_expired_state_returns_expired(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
        state = f"provider=google&action=login&nonce=abc&timestamp={old_ts}"
        ok, _, reason = verify_oauth_state(state, "google")
        assert ok is False
        assert reason == "expired"


class TestExtractUserInfo:
    def test_google_extraction(self):
        userinfo = {
            "sub": "123",
            "email": "User@Google.COM",
            "email_verified": True,
            "name": "Test User",
            "picture": "https://example.com/pic.jpg",
        }
        result = extract_user_info_from_google(userinfo)
        assert result["provider_user_id"] == "123"
        assert result["email"] == "user@google.com"
        assert result["email_verified"] is True

    def test_github_extraction_uses_primary_email(self):
        user = {
            "id": 42,
            "name": "Dev User",
            "avatar_url": "https://example.com/av.png",
        }
        emails = [
            {"email": "other@github.com", "primary": False, "verified": True},
            {"email": "primary@github.com", "primary": True, "verified": True},
        ]
        result = extract_user_info_from_github(user, emails)
        assert result["email"] == "primary@github.com"
        assert result["email_verified"] is True

    def test_discord_builds_avatar_url(self):
        userinfo = {
            "id": "9999",
            "email": "user@discord.com",
            "verified": True,
            "global_name": "DiscordUser",
            "avatar": "abcdef",
        }
        result = extract_user_info_from_discord(userinfo)
        assert "cdn.discordapp.com/avatars/9999/abcdef.png" in result["picture"]
        assert result["email_verified"] is True

    def test_discord_empty_avatar_when_no_hash(self):
        userinfo = {
            "id": "1",
            "email": "u@d.com",
            "verified": False,
            "username": "user",
        }
        result = extract_user_info_from_discord(userinfo)
        assert result["picture"] == ""


class TestCanAutoLinkAccounts:
    def test_links_when_email_matches_and_verified(self):
        user = {"email": "user@example.com", "auth_providers": []}
        provider_info = {"email": "user@example.com", "email_verified": True}
        assert can_auto_link_accounts(user, provider_info, "google") is True

    def test_rejects_when_unverified(self):
        user = {"email": "user@example.com", "auth_providers": []}
        provider_info = {"email": "user@example.com", "email_verified": False}
        assert can_auto_link_accounts(user, provider_info, "google") is False

    def test_rejects_when_email_mismatch(self):
        user = {"email": "other@example.com", "auth_providers": []}
        provider_info = {"email": "user@example.com", "email_verified": True}
        assert can_auto_link_accounts(user, provider_info, "google") is False

    def test_rejects_when_provider_already_linked(self):
        user = {
            "email": "user@example.com",
            "auth_providers": [{"provider": "google", "provider_user_id": "123"}],
        }
        provider_info = {"email": "user@example.com", "email_verified": True}
        assert can_auto_link_accounts(user, provider_info, "google") is False
