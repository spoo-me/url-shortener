"""
Unit tests for Phase 7 — ClickService.

All external dependencies (repositories, GeoIP, cache) are replaced with AsyncMock.
Tests verify:
- v2 click tracking inserts ClickDoc and increments URL click count
- Blocked bots for v2 skip analytics but do NOT raise (redirect still happens)
- Blocked bots for v1/emoji raise ForbiddenError (redirect is also blocked)
- Max-clicks expiry invalidates the URL cache
- GeoIP failure falls back to "Unknown"
- Invalid/missing User-Agent raises ValidationError
- Legacy click builds the correct $inc/$set/$addToSet update document
"""

from __future__ import annotations

import pytest
from typing import Optional
from unittest.mock import AsyncMock, patch
from bson import ObjectId

from errors import ForbiddenError, ValidationError
from infrastructure.cache.url_cache import UrlCacheData
from schemas.models.base import ANONYMOUS_OWNER_ID

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

USER_OID = ObjectId("aaaaaaaaaaaaaaaaaaaaaaaa")
URL_OID = ObjectId("bbbbbbbbbbbbbbbbbbbbbbbb")
ALIAS = "abc1234"
CLIENT_IP = "1.2.3.4"
START_TIME = 0.0
NORMAL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"
)
# Mobile Googlebot UA — has both user_agent AND os in ua_parser (bare Googlebot has os=None).
BOT_UA = (
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/W.X.Y.Z Mobile Safari/537.36 "
    "(compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def make_v2_cache(
    block_bots: bool = False,
    max_clicks: Optional[int] = None,
    owner_id: Optional[str] = None,
) -> UrlCacheData:
    return UrlCacheData(
        _id=str(URL_OID),
        alias=ALIAS,
        long_url="https://example.com",
        block_bots=block_bots,
        password_hash=None,
        expiration_time=None,
        max_clicks=max_clicks,
        url_status="ACTIVE",
        schema_version="v2",
        owner_id=owner_id or str(USER_OID),
    )


def make_v1_cache(
    block_bots: bool = False,
    short_code: str = "abcdef",
) -> UrlCacheData:
    return UrlCacheData(
        _id=short_code,
        alias=short_code,
        long_url="https://legacy.example.com",
        block_bots=block_bots,
        password_hash=None,
        expiration_time=None,
        max_clicks=None,
        url_status="ACTIVE",
        schema_version="v1",
        owner_id=None,
    )


def make_repos_and_geoip():
    click_repo = AsyncMock()
    url_repo = AsyncMock()
    legacy_repo = AsyncMock()
    emoji_repo = AsyncMock()
    geoip = AsyncMock()
    url_cache = AsyncMock()

    # sensible defaults
    geoip.get_country.return_value = "United States"
    geoip.get_city.return_value = "New York"
    url_repo.increment_clicks.return_value = None
    url_repo.expire_if_max_clicks.return_value = False
    click_repo.insert.return_value = None

    return click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache


def make_service(click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache):
    from services.click_service import ClickService

    return ClickService(
        click_repo=click_repo,
        url_repo=url_repo,
        legacy_repo=legacy_repo,
        emoji_repo=emoji_repo,
        geoip=geoip,
        url_cache=url_cache,
    )


# ─────────────────────────────────────────────────────────────────────────────
# TestHandleV2Click
# ─────────────────────────────────────────────────────────────────────────────


class TestHandleV2Click:
    @pytest.mark.asyncio
    async def test_inserts_click_and_increments_url(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v2_cache()
        await svc.handle_v2_click(
            url_data, ALIAS, CLIENT_IP, START_TIME, NORMAL_UA, None
        )

        click_repo.insert.assert_called_once()
        url_repo.increment_clicks.assert_called_once()

    @pytest.mark.asyncio
    async def test_click_doc_has_correct_fields(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v2_cache()
        await svc.handle_v2_click(
            url_data, ALIAS, CLIENT_IP, START_TIME, NORMAL_UA, None
        )

        doc = click_repo.insert.call_args[0][0]
        assert "clicked_at" in doc
        assert "meta" in doc
        assert doc["meta"]["short_code"] == ALIAS
        assert doc["ip_address"] == CLIENT_IP
        assert doc["country"] == "United States"

    @pytest.mark.asyncio
    async def test_blocked_bot_skips_analytics_no_error(self):
        """v2: blocked bot → skip analytics, no exception raised (redirect proceeds)."""
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v2_cache(block_bots=True)

        with patch("shared.bot_detection.is_bot_request", return_value=True):
            # Should NOT raise
            await svc.handle_v2_click(
                url_data, ALIAS, CLIENT_IP, START_TIME, BOT_UA, None
            )

        click_repo.insert.assert_not_called()
        url_repo.increment_clicks.assert_not_called()

    @pytest.mark.asyncio
    async def test_unblocked_bot_still_tracked(self):
        """v2 with block_bots=False: bot is still tracked normally."""
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v2_cache(block_bots=False)

        with patch("shared.bot_detection.is_bot_request", return_value=True):
            with patch("shared.bot_detection.get_bot_name", return_value="Googlebot"):
                await svc.handle_v2_click(
                    url_data, ALIAS, CLIENT_IP, START_TIME, BOT_UA, None
                )

        click_repo.insert.assert_called_once()
        url_repo.increment_clicks.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_clicks_expiry_invalidates_cache(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v2_cache(max_clicks=100)
        url_repo.expire_if_max_clicks.return_value = True  # URL just expired

        await svc.handle_v2_click(
            url_data, ALIAS, CLIENT_IP, START_TIME, NORMAL_UA, None
        )

        url_repo.expire_if_max_clicks.assert_called_once_with(URL_OID, 100)
        url_cache.invalidate.assert_called_once_with(ALIAS)

    @pytest.mark.asyncio
    async def test_max_clicks_not_reached_no_cache_invalidation(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v2_cache(max_clicks=100)
        url_repo.expire_if_max_clicks.return_value = False

        await svc.handle_v2_click(
            url_data, ALIAS, CLIENT_IP, START_TIME, NORMAL_UA, None
        )

        url_cache.invalidate.assert_not_called()

    @pytest.mark.asyncio
    async def test_geoip_failure_falls_back_to_unknown(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        geoip.get_country.return_value = "Unknown"
        geoip.get_city.return_value = None

        url_data = make_v2_cache()
        await svc.handle_v2_click(
            url_data, ALIAS, CLIENT_IP, START_TIME, NORMAL_UA, None
        )

        doc = click_repo.insert.call_args[0][0]
        assert doc["country"] == "Unknown"
        assert doc["city"] == "Unknown"

    @pytest.mark.asyncio
    async def test_cf_city_fallback_when_geoip_returns_none(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        geoip.get_city.return_value = None  # GeoIP city unavailable

        url_data = make_v2_cache()
        await svc.handle_v2_click(
            url_data, ALIAS, CLIENT_IP, START_TIME, NORMAL_UA, None, cf_city="London"
        )

        doc = click_repo.insert.call_args[0][0]
        assert doc["city"] == "London"

    @pytest.mark.asyncio
    async def test_empty_user_agent_raises_validation_error(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v2_cache()
        with pytest.raises(ValidationError):
            await svc.handle_v2_click(url_data, ALIAS, CLIENT_IP, START_TIME, "", None)

    @pytest.mark.asyncio
    async def test_referrer_is_sanitized_in_click_doc(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v2_cache()
        await svc.handle_v2_click(
            url_data,
            ALIAS,
            CLIENT_IP,
            START_TIME,
            NORMAL_UA,
            referrer="https://www.google.com/search?q=test",
        )

        doc = click_repo.insert.call_args[0][0]
        # referrer should be domain only, sanitized
        assert doc["referrer"] == "google.com"

    @pytest.mark.asyncio
    async def test_anonymous_owner_uses_sentinel(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v2_cache(owner_id=None)
        url_data.owner_id = None  # override

        await svc.handle_v2_click(
            url_data, ALIAS, CLIENT_IP, START_TIME, NORMAL_UA, None
        )

        doc = click_repo.insert.call_args[0][0]
        assert doc["meta"]["owner_id"] == ANONYMOUS_OWNER_ID


# ─────────────────────────────────────────────────────────────────────────────
# TestHandleLegacyClick
# ─────────────────────────────────────────────────────────────────────────────


class TestHandleLegacyClick:
    @pytest.mark.asyncio
    async def test_builds_update_doc_and_calls_legacy_repo(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v1_cache(short_code="abcdef")

        with patch("shared.bot_detection.is_bot_request", return_value=False):
            await svc.handle_legacy_click(
                url_data,
                "abcdef",
                is_emoji=False,
                client_ip=CLIENT_IP,
                start_time=START_TIME,
                user_agent=NORMAL_UA,
                referrer=None,
            )

        legacy_repo.update.assert_called_once()
        update_doc = legacy_repo.update.call_args[0][1]
        assert "$inc" in update_doc
        assert "$set" in update_doc
        assert "$addToSet" in update_doc
        assert update_doc["$inc"]["total-clicks"] == 1

    @pytest.mark.asyncio
    async def test_emoji_url_calls_emoji_repo(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v1_cache(short_code="🐍🔥💎")
        url_data.schema_version = "emoji"

        with patch("shared.bot_detection.is_bot_request", return_value=False):
            await svc.handle_legacy_click(
                url_data,
                "🐍🔥💎",
                is_emoji=True,
                client_ip=CLIENT_IP,
                start_time=START_TIME,
                user_agent=NORMAL_UA,
                referrer=None,
            )

        emoji_repo.update.assert_called_once()
        legacy_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocked_bot_v1_raises_forbidden(self):
        """v1: blocked bot → ForbiddenError (redirect is also blocked)."""
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v1_cache(block_bots=True, short_code="abcdef")

        with patch("shared.bot_detection.is_bot_request", return_value=True):
            with pytest.raises(ForbiddenError):
                await svc.handle_legacy_click(
                    url_data,
                    "abcdef",
                    is_emoji=False,
                    client_ip=CLIENT_IP,
                    start_time=START_TIME,
                    user_agent=BOT_UA,
                    referrer=None,
                )

        legacy_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_unblocked_bot_v1_tracked_no_error(self):
        """v1 with block_bots=False: bot is counted but no exception."""
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v1_cache(block_bots=False, short_code="abcdef")

        with patch("shared.bot_detection.is_bot_request", return_value=True):
            with patch("shared.bot_detection.get_bot_name", return_value="Googlebot"):
                await svc.handle_legacy_click(
                    url_data,
                    "abcdef",
                    is_emoji=False,
                    client_ip=CLIENT_IP,
                    start_time=START_TIME,
                    user_agent=BOT_UA,
                    referrer=None,
                )

        legacy_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_user_agent_raises_validation_error(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v1_cache()
        with pytest.raises(ValidationError):
            await svc.handle_legacy_click(
                url_data,
                "abcdef",
                is_emoji=False,
                client_ip=CLIENT_IP,
                start_time=START_TIME,
                user_agent="",
                referrer=None,
            )

    @pytest.mark.asyncio
    async def test_referrer_added_to_update_doc(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v1_cache(short_code="abcdef")

        with patch("shared.bot_detection.is_bot_request", return_value=False):
            await svc.handle_legacy_click(
                url_data,
                "abcdef",
                is_emoji=False,
                client_ip=CLIENT_IP,
                start_time=START_TIME,
                user_agent=NORMAL_UA,
                referrer="https://www.twitter.com/home",
            )

        update_doc = legacy_repo.update.call_args[0][1]
        inc_keys = list(update_doc["$inc"].keys())
        referrer_keys = [k for k in inc_keys if k.startswith("referrer.")]
        assert len(referrer_keys) > 0

    @pytest.mark.asyncio
    async def test_last_click_metadata_in_set(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v1_cache(short_code="abcdef")

        with patch("shared.bot_detection.is_bot_request", return_value=False):
            await svc.handle_legacy_click(
                url_data,
                "abcdef",
                is_emoji=False,
                client_ip=CLIENT_IP,
                start_time=START_TIME,
                user_agent=NORMAL_UA,
                referrer=None,
            )

        update_doc = legacy_repo.update.call_args[0][1]
        assert "last-click" in update_doc["$set"]
        assert "last-click-browser" in update_doc["$set"]
        assert "last-click-os" in update_doc["$set"]
        assert "average_redirection_time" in update_doc["$set"]

    @pytest.mark.asyncio
    async def test_unique_click_counter_incremented(self):
        """Every click is treated as unique since ips are not tracked in UrlCacheData."""
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v1_cache(short_code="abcdef")

        with patch("shared.bot_detection.is_bot_request", return_value=False):
            await svc.handle_legacy_click(
                url_data,
                "abcdef",
                is_emoji=False,
                client_ip=CLIENT_IP,
                start_time=START_TIME,
                user_agent=NORMAL_UA,
                referrer=None,
            )

        update_doc = legacy_repo.update.call_args[0][1]
        unique_keys = [k for k in update_doc["$inc"] if k.startswith("unique_counter.")]
        assert len(unique_keys) == 1


# ─────────────────────────────────────────────────────────────────────────────
# TestTrackClickDispatch
# ─────────────────────────────────────────────────────────────────────────────


class TestTrackClickDispatch:
    @pytest.mark.asyncio
    async def test_dispatches_v2_schema_to_handle_v2_click(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v2_cache()

        with patch.object(svc, "handle_v2_click", new_callable=AsyncMock) as mock_v2:
            await svc.track_click(
                url_data,
                ALIAS,
                schema="v2",
                is_emoji=False,
                client_ip=CLIENT_IP,
                start_time=START_TIME,
                user_agent=NORMAL_UA,
                referrer=None,
            )
            mock_v2.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatches_v1_schema_to_handle_legacy_click(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v1_cache()

        with patch.object(
            svc, "handle_legacy_click", new_callable=AsyncMock
        ) as mock_legacy:
            await svc.track_click(
                url_data,
                "abcdef",
                schema="v1",
                is_emoji=False,
                client_ip=CLIENT_IP,
                start_time=START_TIME,
                user_agent=NORMAL_UA,
                referrer=None,
            )
            mock_legacy.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatches_emoji_schema_to_handle_legacy_with_is_emoji_true(self):
        click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache = (
            make_repos_and_geoip()
        )
        svc = make_service(
            click_repo, url_repo, legacy_repo, emoji_repo, geoip, url_cache
        )

        url_data = make_v1_cache()
        url_data.schema_version = "emoji"

        with patch.object(
            svc, "handle_legacy_click", new_callable=AsyncMock
        ) as mock_legacy:
            await svc.track_click(
                url_data,
                "🐍🔥💎",
                schema="emoji",
                is_emoji=True,
                client_ip=CLIENT_IP,
                start_time=START_TIME,
                user_agent=NORMAL_UA,
                referrer=None,
            )
            mock_legacy.assert_called_once()
            _, kwargs = mock_legacy.call_args
            # is_emoji should be passed correctly
            assert mock_legacy.call_args[0][2] is True or (
                "is_emoji" in mock_legacy.call_args[1]
                and mock_legacy.call_args[1]["is_emoji"] is True
            )
