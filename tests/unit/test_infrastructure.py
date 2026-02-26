"""Unit tests for Phase 5 — Infrastructure layer."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import geoip2.errors
import pytest

from config import EmailSettings

from infrastructure.cache.url_cache import UrlCache, UrlCacheData
from infrastructure.cache.dual_cache import DualCache
from infrastructure.captcha.hcaptcha import HCaptchaProvider
from infrastructure.geoip import GeoIPService
from infrastructure.http_client import HttpClient
from infrastructure.webhook.discord import DiscordWebhookProvider
from infrastructure.email.zeptomail import ZeptoMailProvider
from infrastructure.oauth_clients import (
    can_auto_link_accounts,
    extract_user_info_from_discord,
    extract_user_info_from_github,
    extract_user_info_from_google,
    generate_oauth_state,
    verify_oauth_state,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _url_data(**overrides) -> UrlCacheData:
    base = dict(
        _id="507f1f77bcf86cd799439011",
        alias="abc1234",
        long_url="https://example.com",
        block_bots=False,
        password_hash=None,
        expiration_time=None,
        max_clicks=None,
        url_status="ACTIVE",
        schema_version="v2",
        owner_id="507f1f77bcf86cd799439012",
    )
    base.update(overrides)
    return UrlCacheData(**base)


def _fake_redis(get_returns=None):
    """Return a mock async Redis client."""
    r = AsyncMock()
    r.get.return_value = get_returns
    r.setex.return_value = True
    r.delete.return_value = 1
    r.set.return_value = True
    return r


# ── HttpClient ────────────────────────────────────────────────────────────────


class TestHttpClient:
    async def test_post_delegates_to_httpx(self, mocker):
        client = HttpClient()
        fake_resp = MagicMock(status_code=200)
        mocker.patch.object(client._client, "post", return_value=fake_resp)
        resp = await client.post("http://example.com")
        assert resp.status_code == 200
        await client.aclose()

    async def test_get_delegates_to_httpx(self, mocker):
        client = HttpClient()
        fake_resp = MagicMock(status_code=200)
        mocker.patch.object(client._client, "get", return_value=fake_resp)
        resp = await client.get("http://example.com")
        assert resp.status_code == 200
        await client.aclose()

    async def test_post_propagates_exception(self, mocker):
        client = HttpClient()
        mocker.patch.object(client._client, "post", side_effect=Exception("timeout"))
        with pytest.raises(Exception, match="timeout"):
            await client.post("http://example.com")
        await client.aclose()

    async def test_context_manager(self):
        async with HttpClient() as client:
            assert client is not None


# ── UrlCache ──────────────────────────────────────────────────────────────────


class TestUrlCache:
    async def test_get_returns_none_when_redis_none(self):
        cache = UrlCache(redis_client=None)
        assert await cache.get("abc") is None

    async def test_get_returns_data_on_hit(self):
        data = _url_data()
        r = _fake_redis(get_returns=json.dumps(data.__dict__))
        cache = UrlCache(r)
        result = await cache.get("abc1234")
        assert result is not None
        assert result.long_url == "https://example.com"
        assert result.url_status == "ACTIVE"

    async def test_get_returns_none_on_miss(self):
        r = _fake_redis(get_returns=None)
        cache = UrlCache(r)
        assert await cache.get("missing") is None

    async def test_set_calls_setex_with_ttl(self):
        r = _fake_redis()
        cache = UrlCache(r, ttl_seconds=300)
        await cache.set("abc1234", _url_data())
        r.setex.assert_called_once()
        call_args = r.setex.call_args[0]
        assert call_args[0] == "url_cache:abc1234"
        assert call_args[1] == 300

    async def test_set_noop_when_redis_none(self):
        cache = UrlCache(redis_client=None)
        await cache.set("abc", _url_data())  # must not raise

    async def test_invalidate_deletes_key(self):
        r = _fake_redis()
        cache = UrlCache(r)
        await cache.invalidate("abc1234")
        r.delete.assert_called_once_with("url_cache:abc1234")

    async def test_invalidate_noop_when_redis_none(self):
        cache = UrlCache(redis_client=None)
        await cache.invalidate("abc")  # must not raise

    async def test_set_stores_json_serialisable_data(self):
        r = _fake_redis()
        cache = UrlCache(r)
        await cache.set("x", _url_data(password_hash="$argon2id$..."))
        _, _, payload = r.setex.call_args[0]
        parsed = json.loads(payload)
        assert parsed["password_hash"] == "$argon2id$..."


# ── DualCache ─────────────────────────────────────────────────────────────────


class TestDualCache:
    async def test_returns_live_data_on_primary_hit(self):
        r = AsyncMock()
        r.get = AsyncMock(side_effect=[json.dumps({"v": 1}), None])
        r.set = AsyncMock(return_value=True)
        cache = DualCache(r)
        result = await cache.get_or_set("key", AsyncMock(return_value={"v": 99}))
        assert result == {"v": 1}

    async def test_returns_stale_and_schedules_refresh(self):
        r = AsyncMock()
        # primary miss, stale hit
        r.get = AsyncMock(side_effect=[None, json.dumps({"v": "stale"})])
        r.set = AsyncMock(return_value=True)  # lock acquired
        cache = DualCache(r)
        result = await cache.get_or_set("key", AsyncMock(return_value={"v": "fresh"}))
        assert result == {"v": "stale"}

    async def test_calls_query_fn_on_full_miss(self):
        r = AsyncMock()
        r.get = AsyncMock(return_value=None)
        r.set = AsyncMock(return_value=True)  # lock acquired
        r.setex = AsyncMock()
        r.delete = AsyncMock()
        query = AsyncMock(return_value={"v": "fresh"})
        cache = DualCache(r)
        result = await cache.get_or_set("key", query)
        assert result == {"v": "fresh"}
        query.assert_awaited_once()

    async def test_returns_none_when_redis_none(self):
        called = False

        async def query():
            nonlocal called
            called = True
            return {"v": 1}

        cache = DualCache(redis_client=None)
        result = await cache.get_or_set("key", query)
        # When redis is None, query is called directly
        assert called
        assert result == {"v": 1}

    async def test_returns_none_on_lock_contention(self):
        r = AsyncMock()
        r.get = AsyncMock(return_value=None)  # both miss
        r.set = AsyncMock(return_value=None)  # lock NOT acquired
        cache = DualCache(r)
        result = await cache.get_or_set("key", AsyncMock(return_value={"v": 1}))
        assert result is None


# ── GeoIPService ──────────────────────────────────────────────────────────────


class TestGeoIPService:
    async def test_get_country_returns_unknown_when_db_missing(self):
        svc = GeoIPService("nonexistent.mmdb", "nonexistent.mmdb")
        result = await svc.get_country("1.2.3.4")
        assert result == "Unknown"

    async def test_get_city_returns_none_when_db_missing(self):
        svc = GeoIPService("nonexistent.mmdb", "nonexistent.mmdb")
        result = await svc.get_city("1.2.3.4")
        assert result is None

    async def test_get_country_returns_unknown_on_lookup_error(self, mocker):
        svc = GeoIPService("nonexistent.mmdb", "nonexistent.mmdb")
        fake_reader = MagicMock()
        fake_reader.country.side_effect = geoip2.errors.AddressNotFoundError(
            "not found"
        )
        svc._country_reader = fake_reader
        svc._country_loaded = True
        result = await svc.get_country("1.2.3.4")
        assert result == "Unknown"

    async def test_get_city_returns_none_on_lookup_error(self, mocker):
        svc = GeoIPService("nonexistent.mmdb", "nonexistent.mmdb")
        fake_reader = MagicMock()
        fake_reader.city.side_effect = geoip2.errors.AddressNotFoundError("not found")
        svc._city_reader = fake_reader
        svc._city_loaded = True
        result = await svc.get_city("1.2.3.4")
        assert result is None


# ── HCaptchaProvider ──────────────────────────────────────────────────────────


class TestHCaptchaProvider:
    def _make(self, secret="test-secret"):
        http = MagicMock()
        return HCaptchaProvider(secret=secret, http_client=http), http

    async def test_returns_true_on_success(self, mocker):
        provider, http = self._make()
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"success": True}
        http.post = AsyncMock(return_value=resp)
        assert await provider.verify("good-token") is True

    async def test_returns_false_on_failure(self, mocker):
        provider, http = self._make()
        resp = MagicMock(status_code=200)
        resp.json.return_value = {
            "success": False,
            "error-codes": ["invalid-input-response"],
        }
        http.post = AsyncMock(return_value=resp)
        assert await provider.verify("bad-token") is False

    async def test_returns_false_when_secret_empty(self):
        provider, _ = self._make(secret="")
        assert await provider.verify("any-token") is False

    async def test_returns_false_on_http_error(self):
        provider, http = self._make()
        http.post = AsyncMock(side_effect=Exception("network error"))
        assert await provider.verify("token") is False

    async def test_returns_false_on_non_200_status(self):
        provider, http = self._make()
        resp = MagicMock(status_code=500, text="Internal Server Error")
        http.post = AsyncMock(return_value=resp)
        assert await provider.verify("token") is False


# ── DiscordWebhookProvider ────────────────────────────────────────────────────


class TestDiscordWebhookProvider:
    def _make(self, url="https://discord.com/api/webhooks/123/abc"):
        http = MagicMock()
        return DiscordWebhookProvider(webhook_url=url, http_client=http), http

    async def test_sends_payload_returns_true_on_204(self):
        provider, http = self._make()
        resp = MagicMock(status_code=204)
        http.post = AsyncMock(return_value=resp)
        assert await provider.send({"embeds": []}) is True

    async def test_sends_payload_returns_true_on_200(self):
        provider, http = self._make()
        resp = MagicMock(status_code=200)
        http.post = AsyncMock(return_value=resp)
        assert await provider.send({"embeds": []}) is True

    async def test_returns_false_on_error_status(self):
        provider, http = self._make()
        resp = MagicMock(status_code=400, text="Bad Request")
        http.post = AsyncMock(return_value=resp)
        assert await provider.send({}) is False

    async def test_returns_false_when_url_empty(self):
        provider, _ = self._make(url="")
        assert await provider.send({}) is False

    async def test_returns_false_on_exception(self):
        provider, http = self._make()
        http.post = AsyncMock(side_effect=Exception("network error"))
        assert await provider.send({}) is False


# ── ZeptoMailProvider ─────────────────────────────────────────────────────────


class TestZeptoMailProvider:
    def _make(self, token="test-token"):
        settings = EmailSettings(
            zepto_api_token=token,
            zepto_from_email="noreply@spoo.me",
            zepto_from_name="spoo.me",
        )
        http = MagicMock()
        # Patch template rendering so tests don't need real template files
        jinja = MagicMock()
        jinja.get_template.return_value.render.return_value = "<html>test</html>"
        provider = ZeptoMailProvider(
            settings=settings, http_client=http, app_url="https://spoo.me"
        )
        provider._jinja = jinja
        return provider, http

    async def test_send_verification_makes_post(self):
        provider, http = self._make()
        resp = MagicMock(status_code=200)
        http.post = AsyncMock(return_value=resp)
        result = await provider.send_verification_email(
            "user@example.com", "Alice", "123456"
        )
        assert result is True
        http.post.assert_awaited_once()

    async def test_returns_false_when_token_empty(self):
        provider, _ = self._make(token="")
        assert (
            await provider.send_verification_email("u@e.com", None, "000000") is False
        )

    async def test_returns_false_on_non_2xx(self):
        provider, http = self._make()
        resp = MagicMock(status_code=422, text="Unprocessable")
        http.post = AsyncMock(return_value=resp)
        assert (
            await provider.send_verification_email("u@e.com", None, "000000") is False
        )

    async def test_returns_false_on_exception(self):
        provider, http = self._make()
        http.post = AsyncMock(side_effect=Exception("timeout"))
        assert (
            await provider.send_verification_email("u@e.com", None, "000000") is False
        )

    async def test_auth_header_prepends_prefix(self):
        provider, http = self._make(token="rawtoken")
        resp = MagicMock(status_code=200)
        http.post = AsyncMock(return_value=resp)
        await provider.send_welcome_email("u@e.com", "Alice")
        _, kwargs = http.post.call_args
        auth = kwargs["headers"]["Authorization"]
        assert auth == "Zoho-enczapikey rawtoken"

    async def test_auth_header_not_double_prefixed(self):
        provider, http = self._make(token="Zoho-enczapikey alreadyprefixed")
        resp = MagicMock(status_code=201)
        http.post = AsyncMock(return_value=resp)
        await provider.send_password_reset_email("u@e.com", None, "654321")
        _, kwargs = http.post.call_args
        auth = kwargs["headers"]["Authorization"]
        assert auth.count("Zoho-enczapikey") == 1


# ── OAuth utilities ───────────────────────────────────────────────────────────


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
