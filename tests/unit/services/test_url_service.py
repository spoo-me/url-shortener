"""
Unit tests for Phase 7 — UrlService.

All external dependencies (repositories, cache) are replaced with AsyncMock.
Tests verify behavior, not implementation details.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from errors import (
    BlockedUrlError,
    ConflictError,
    ForbiddenError,
    GoneError,
    NotFoundError,
    ValidationError,
)
from infrastructure.cache.url_cache import UrlCacheData
from schemas.models.base import ANONYMOUS_OWNER_ID
from schemas.models.url import EmojiUrlDoc, LegacyUrlDoc, UrlV2Doc

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

USER_OID = ObjectId("aaaaaaaaaaaaaaaaaaaaaaaa")
URL_OID = ObjectId("bbbbbbbbbbbbbbbbbbbbbbbb")
ALIAS = "abc1234"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def make_url_v2_doc(
    alias: str = ALIAS,
    url_id: ObjectId = URL_OID,
    owner_id: ObjectId = USER_OID,
    status: str = "ACTIVE",
    block_bots: bool | None = None,
    max_clicks: int | None = None,
    password: str | None = None,
    expire_after: datetime | None = None,
) -> UrlV2Doc:
    return UrlV2Doc.from_mongo(
        {
            "_id": url_id,
            "alias": alias,
            "owner_id": owner_id,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "creation_ip": "1.2.3.4",
            "long_url": "https://example.com",
            "password": password,
            "block_bots": block_bots,
            "max_clicks": max_clicks,
            "expire_after": expire_after,
            "status": status,
            "private_stats": True,
            "total_clicks": 0,
            "last_click": None,
        }
    )


def make_legacy_doc(
    short_code: str = "abcdef",
    url: str = "https://legacy.example.com",
    block_bots: bool = False,
    max_clicks: int | None = None,
    password: str | None = None,
) -> LegacyUrlDoc:
    return LegacyUrlDoc.from_mongo(
        {
            "_id": short_code,
            "url": url,
            "block-bots": block_bots,
            "max-clicks": max_clicks,
            "total-clicks": 0,
            "password": password,
        }
    )


def make_emoji_doc(short_code: str = "🐍🔥💎") -> EmojiUrlDoc:
    return EmojiUrlDoc.from_mongo(
        {
            "_id": short_code,
            "url": "https://emoji.example.com",
            "block-bots": False,
            "total-clicks": 0,
        }
    )


def make_active_cache(
    schema: str = "v2",
    alias: str = ALIAS,
    block_bots: bool = False,
    max_clicks: int | None = None,
    password_hash: str | None = None,
) -> UrlCacheData:
    return UrlCacheData(
        _id=str(URL_OID),
        alias=alias,
        long_url="https://example.com",
        block_bots=block_bots,
        password_hash=password_hash,
        expiration_time=None,
        max_clicks=max_clicks,
        url_status="ACTIVE",
        schema_version=schema,
        owner_id=str(USER_OID),
    )


def make_repos():
    url_repo = AsyncMock()
    legacy_repo = AsyncMock()
    emoji_repo = AsyncMock()
    blocked_url_repo = AsyncMock()
    url_cache = AsyncMock()
    return url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache


def make_service(url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache):
    from services.url_service import UrlService

    return UrlService(
        url_repo=url_repo,
        legacy_repo=legacy_repo,
        emoji_repo=emoji_repo,
        blocked_url_repo=blocked_url_repo,
        url_cache=url_cache,
        blocked_self_domains=["spoo.me"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# TestUrlServiceResolve
# ─────────────────────────────────────────────────────────────────────────────


class TestUrlServiceResolve:
    @pytest.mark.asyncio
    async def test_cache_hit_active_v2_returns_data(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        cached = make_active_cache(schema="v2")
        url_cache.get.return_value = cached

        result, schema = await svc.resolve(ALIAS)

        assert result is cached
        assert schema == "v2"
        url_repo.find_by_alias.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_hit_blocked_v2_raises_blocked_url_error(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        cached = UrlCacheData(
            _id=str(URL_OID),
            alias=ALIAS,
            long_url="",
            block_bots=False,
            password_hash=None,
            expiration_time=None,
            max_clicks=None,
            url_status="BLOCKED",
            schema_version="v2",
            owner_id=str(USER_OID),
        )
        url_cache.get.return_value = cached

        with pytest.raises(BlockedUrlError):
            await svc.resolve(ALIAS)

    @pytest.mark.asyncio
    async def test_cache_hit_expired_v2_raises_gone(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        for status in ("EXPIRED", "INACTIVE"):
            url_cache.get.return_value = UrlCacheData(
                _id=str(URL_OID),
                alias=ALIAS,
                long_url="",
                block_bots=False,
                password_hash=None,
                expiration_time=None,
                max_clicks=None,
                url_status=status,
                schema_version="v2",
                owner_id=str(USER_OID),
            )
            with pytest.raises(GoneError):
                await svc.resolve(ALIAS)

    @pytest.mark.asyncio
    async def test_cache_miss_7char_tries_v2_first(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_cache.get.return_value = None
        doc = make_url_v2_doc(alias="abc1234")
        url_repo.find_by_alias.return_value = doc

        result, schema = await svc.resolve("abc1234")

        assert schema == "v2"
        assert result.alias == "abc1234"
        url_repo.find_by_alias.assert_called_once_with("abc1234")
        legacy_repo.find_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_7char_falls_back_to_v1(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_cache.get.return_value = None
        url_repo.find_by_alias.return_value = None
        doc = make_legacy_doc(short_code="abc1234")
        legacy_repo.find_by_id.return_value = doc

        _result, schema = await svc.resolve("abc1234")

        assert schema == "v1"
        url_repo.find_by_alias.assert_called_once_with("abc1234")
        legacy_repo.find_by_id.assert_called_once_with("abc1234")

    @pytest.mark.asyncio
    async def test_cache_miss_6char_tries_v1_first(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_cache.get.return_value = None
        doc = make_legacy_doc(short_code="abcdef")
        legacy_repo.find_by_id.return_value = doc

        _result, schema = await svc.resolve("abcdef")

        assert schema == "v1"
        legacy_repo.find_by_id.assert_called_once_with("abcdef")
        url_repo.find_by_alias.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_6char_falls_back_to_v2(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_cache.get.return_value = None
        legacy_repo.find_by_id.return_value = None
        doc = make_url_v2_doc(alias="abcdef")
        url_repo.find_by_alias.return_value = doc

        _result, schema = await svc.resolve("abcdef")

        assert schema == "v2"
        legacy_repo.find_by_id.assert_called_once_with("abcdef")
        url_repo.find_by_alias.assert_called_once_with("abcdef")

    @pytest.mark.asyncio
    async def test_cache_miss_emoji_resolves_emoji_schema(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_cache.get.return_value = None
        emoji_doc = make_emoji_doc("🐍🔥💎")
        emoji_repo.find_by_id.return_value = emoji_doc

        _result, schema = await svc.resolve("🐍🔥💎")

        assert schema == "emoji"
        emoji_repo.find_by_id.assert_called_once_with("🐍🔥💎")
        url_repo.find_by_alias.assert_not_called()
        legacy_repo.find_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_other_length_tries_v2_first(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_cache.get.return_value = None
        doc = make_url_v2_doc(alias="customalias")
        url_repo.find_by_alias.return_value = doc

        _result, schema = await svc.resolve("customalias")

        assert schema == "v2"
        url_repo.find_by_alias.assert_called_once_with("customalias")

    @pytest.mark.asyncio
    async def test_cache_miss_not_found_raises_not_found(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_cache.get.return_value = None
        url_repo.find_by_alias.return_value = None
        legacy_repo.find_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await svc.resolve("missing")

    @pytest.mark.asyncio
    async def test_db_miss_v2_blocked_caches_minimal_then_raises(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_cache.get.return_value = None
        blocked_doc = make_url_v2_doc(alias=ALIAS, status="BLOCKED")
        url_repo.find_by_alias.return_value = blocked_doc

        with pytest.raises(BlockedUrlError):
            await svc.resolve(ALIAS)

        # Cache should have been populated (even for blocked URLs)
        url_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_v1_with_max_clicks_not_cached(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_cache.get.return_value = None
        legacy_repo.find_by_id.return_value = make_legacy_doc(
            short_code="abcdef", max_clicks=10
        )

        await svc.resolve("abcdef")

        url_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_v1_without_max_clicks_is_cached(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_cache.get.return_value = None
        legacy_repo.find_by_id.return_value = make_legacy_doc(short_code="abcdef")

        await svc.resolve("abcdef")

        url_cache.set.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# TestUrlServiceCreate
# ─────────────────────────────────────────────────────────────────────────────


class TestUrlServiceCreate:
    @pytest.mark.asyncio
    async def test_creates_url_with_generated_alias(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        blocked_url_repo.get_patterns.return_value = []
        url_repo.check_alias_exists.return_value = False
        url_repo.insert.return_value = URL_OID

        from schemas.dto.requests.url import CreateUrlRequest

        req = CreateUrlRequest(long_url="https://example.com")
        result, _ = await svc.create(req, owner_id=USER_OID, client_ip="1.2.3.4")
        assert result.long_url == "https://example.com"
        url_repo.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_custom_alias_checks_v2_uniqueness(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        blocked_url_repo.get_patterns.return_value = []
        # Alias does NOT exist in v2 or v1
        url_repo.check_alias_exists.return_value = False
        legacy_repo.check_exists.return_value = False
        url_repo.insert.return_value = URL_OID

        from schemas.dto.requests.url import CreateUrlRequest

        req = CreateUrlRequest(long_url="https://example.com", alias="myalias")
        await svc.create(req, owner_id=USER_OID, client_ip="1.2.3.4")

        url_repo.check_alias_exists.assert_called_with("myalias")

    @pytest.mark.asyncio
    async def test_create_with_custom_alias_checks_v1_uniqueness(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        blocked_url_repo.get_patterns.return_value = []
        # Not in v2
        url_repo.check_alias_exists.return_value = False
        # Exists in v1 → should reject
        legacy_repo.check_exists.return_value = True

        from schemas.dto.requests.url import CreateUrlRequest

        req = CreateUrlRequest(long_url="https://example.com", alias="myalias")
        with pytest.raises(ConflictError):
            await svc.create(req, owner_id=USER_OID, client_ip="1.2.3.4")

    @pytest.mark.asyncio
    async def test_create_blocked_url_raises_validation_error(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        blocked_url_repo.get_patterns.return_value = [r"https://evil\.com"]

        from schemas.dto.requests.url import CreateUrlRequest

        req = CreateUrlRequest(long_url="https://evil.com/page")
        with pytest.raises(ValidationError):
            await svc.create(req, owner_id=USER_OID, client_ip="1.2.3.4")

    @pytest.mark.asyncio
    async def test_create_self_link_raises_validation_error(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        blocked_url_repo.get_patterns.return_value = []

        from schemas.dto.requests.url import CreateUrlRequest

        req = CreateUrlRequest(long_url="https://spoo.me/abc")
        with pytest.raises(ValidationError):
            await svc.create(req, owner_id=USER_OID, client_ip="1.2.3.4")

    @pytest.mark.asyncio
    async def test_create_hashes_password(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        blocked_url_repo.get_patterns.return_value = []
        url_repo.check_alias_exists.return_value = False
        url_repo.insert.return_value = URL_OID

        from schemas.dto.requests.url import CreateUrlRequest

        req = CreateUrlRequest(long_url="https://example.com", password="Secret1!")
        await svc.create(req, owner_id=USER_OID, client_ip="1.2.3.4")

        # password in DB doc should be a hash, not plaintext
        inserted_doc = url_repo.insert.call_args[0][0]
        assert inserted_doc["password"] != "Secret1!"
        assert inserted_doc["password"] is not None

    @pytest.mark.asyncio
    async def test_create_anonymous_owner_uses_sentinel(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        blocked_url_repo.get_patterns.return_value = []
        url_repo.check_alias_exists.return_value = False  # needed for alias generation
        url_repo.insert.return_value = URL_OID

        from schemas.dto.requests.url import CreateUrlRequest

        req = CreateUrlRequest(long_url="https://example.com")
        await svc.create(req, owner_id=None, client_ip="1.2.3.4")

        inserted_doc = url_repo.insert.call_args[0][0]
        assert inserted_doc["owner_id"] == ANONYMOUS_OWNER_ID

    @pytest.mark.asyncio
    async def test_create_future_expire_after_is_accepted(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        blocked_url_repo.get_patterns.return_value = []
        url_repo.check_alias_exists.return_value = False
        url_repo.insert.return_value = URL_OID

        from schemas.dto.requests.url import CreateUrlRequest

        # far future unix timestamp
        future_ts = 9999999999
        req = CreateUrlRequest(long_url="https://example.com", expire_after=future_ts)
        await svc.create(req, owner_id=USER_OID, client_ip="1.2.3.4")

        inserted_doc = url_repo.insert.call_args[0][0]
        assert inserted_doc["expire_after"] is not None

    @pytest.mark.asyncio
    async def test_create_past_expire_after_raises_validation_error(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        blocked_url_repo.get_patterns.return_value = []

        from schemas.dto.requests.url import CreateUrlRequest

        past_ts = 1000000  # very old timestamp
        req = CreateUrlRequest(long_url="https://example.com", expire_after=past_ts)
        with pytest.raises(ValidationError):
            await svc.create(req, owner_id=USER_OID, client_ip="1.2.3.4")


# ─────────────────────────────────────────────────────────────────────────────
# TestUrlServiceUpdate
# ─────────────────────────────────────────────────────────────────────────────


class TestUrlServiceUpdate:
    @pytest.mark.asyncio
    async def test_update_changes_field_and_invalidates_cache(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc()
        url_repo.find_by_id.return_value = existing
        url_repo.update.return_value = True

        from schemas.dto.requests.url import UpdateUrlRequest

        req = UpdateUrlRequest(long_url="https://new-url.com")
        await svc.update(URL_OID, req, USER_OID)

        url_repo.update.assert_called_once()
        update_doc = url_repo.update.call_args[0][1]
        assert "$set" in update_doc
        assert "long_url" in update_doc["$set"]
        url_cache.invalidate.assert_called_once_with(ALIAS)

    @pytest.mark.asyncio
    async def test_update_no_changes_returns_existing(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc()
        url_repo.find_by_id.return_value = existing

        from schemas.dto.requests.url import UpdateUrlRequest

        # Send same long_url — no actual change
        req = UpdateUrlRequest(long_url="https://example.com")
        await svc.update(URL_OID, req, USER_OID)

        url_repo.update.assert_not_called()
        url_cache.invalidate.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_wrong_owner_raises_forbidden(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc(owner_id=USER_OID)
        url_repo.find_by_id.return_value = existing

        other_user = ObjectId("eeeeeeeeeeeeeeeeeeeeeeee")

        from schemas.dto.requests.url import UpdateUrlRequest

        req = UpdateUrlRequest(long_url="https://new-url.com")
        with pytest.raises(ForbiddenError):
            await svc.update(URL_OID, req, other_user)

    @pytest.mark.asyncio
    async def test_update_not_found_raises_not_found(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_repo.find_by_id.return_value = None

        from schemas.dto.requests.url import UpdateUrlRequest

        req = UpdateUrlRequest(long_url="https://new-url.com")
        with pytest.raises(NotFoundError):
            await svc.update(URL_OID, req, USER_OID)

    @pytest.mark.asyncio
    async def test_update_alias_conflict_raises_conflict(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc()
        url_repo.find_by_id.return_value = existing
        # New alias already exists in v2
        url_repo.check_alias_exists.return_value = True

        from schemas.dto.requests.url import UpdateUrlRequest

        req = UpdateUrlRequest(alias="taken")
        with pytest.raises(ConflictError):
            await svc.update(URL_OID, req, USER_OID)

    @pytest.mark.asyncio
    async def test_update_blocked_url_raises_forbidden(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc(status="BLOCKED")
        url_repo.find_by_id.return_value = existing

        from schemas.dto.requests.url import UpdateUrlRequest

        req = UpdateUrlRequest(long_url="https://new-url.com")
        with pytest.raises(ForbiddenError, match="Cannot modify a blocked URL"):
            await svc.update(URL_OID, req, USER_OID)

        url_repo.update.assert_not_called()
        url_cache.invalidate.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_blocked_url_status_change_raises_forbidden(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc(status="BLOCKED")
        url_repo.find_by_id.return_value = existing

        from schemas.dto.requests.url import UpdateUrlRequest

        req = UpdateUrlRequest(status="ACTIVE")
        with pytest.raises(ForbiddenError, match="Cannot modify a blocked URL"):
            await svc.update(URL_OID, req, USER_OID)

        url_repo.update.assert_not_called()
        url_cache.invalidate.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# TestUrlServiceDelete
# ─────────────────────────────────────────────────────────────────────────────


class TestUrlServiceDelete:
    @pytest.mark.asyncio
    async def test_delete_success_invalidates_cache(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc()
        url_repo.find_by_id.return_value = existing
        url_repo.delete.return_value = True

        await svc.delete(URL_OID, USER_OID)

        url_repo.delete.assert_called_once_with(URL_OID)
        url_cache.invalidate.assert_called_once_with(ALIAS)

    @pytest.mark.asyncio
    async def test_delete_wrong_owner_raises_forbidden(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc(owner_id=USER_OID)
        url_repo.find_by_id.return_value = existing

        other_user = ObjectId("eeeeeeeeeeeeeeeeeeeeeeee")
        with pytest.raises(ForbiddenError):
            await svc.delete(URL_OID, other_user)

        url_repo.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_not_found_raises_not_found(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_repo.find_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await svc.delete(URL_OID, USER_OID)

    @pytest.mark.asyncio
    async def test_delete_blocked_url_raises_forbidden(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc(status="BLOCKED")
        url_repo.find_by_id.return_value = existing

        with pytest.raises(ForbiddenError, match="Cannot delete a blocked URL"):
            await svc.delete(URL_OID, USER_OID)

        url_repo.delete.assert_not_called()
        url_cache.invalidate.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# TestCheckAliasAvailable
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckAliasAvailable:
    @pytest.mark.asyncio
    async def test_available_when_not_in_v2_or_v1(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_repo.check_alias_exists.return_value = False
        legacy_repo.check_exists.return_value = False

        assert await svc.check_alias_available("newcode") is True

    @pytest.mark.asyncio
    async def test_unavailable_when_in_v2(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_repo.check_alias_exists.return_value = True

        assert await svc.check_alias_available("taken") is False
        legacy_repo.check_exists.assert_not_called()

    @pytest.mark.asyncio
    async def test_unavailable_when_in_v1(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_repo.check_alias_exists.return_value = False
        legacy_repo.check_exists.return_value = True

        assert await svc.check_alias_available("v1code") is False


# ─────────────────────────────────────────────────────────────────────────────
# TestUrlServiceUpdate
# ─────────────────────────────────────────────────────────────────────────────


class TestUrlServiceUpdateEdgeCases:
    @pytest.mark.asyncio
    async def test_update_not_found_raises(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_repo.find_by_id.return_value = None
        from schemas.dto.requests.url import UpdateUrlRequest

        with pytest.raises(NotFoundError):
            await svc.update(URL_OID, UpdateUrlRequest(), USER_OID)

    @pytest.mark.asyncio
    async def test_update_forbidden_raises(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        other_user = ObjectId("bbbbbbbbbbbbbbbbbbbbbbbb")
        url_repo.find_by_id.return_value = make_url_v2_doc(owner_id=other_user)
        from schemas.dto.requests.url import UpdateUrlRequest

        with pytest.raises(ForbiddenError):
            await svc.update(URL_OID, UpdateUrlRequest(), USER_OID)

    @pytest.mark.asyncio
    async def test_update_no_op_returns_existing(self):
        """When nothing changes, update() returns the existing doc without hitting the DB."""
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc()
        url_repo.find_by_id.return_value = existing
        from schemas.dto.requests.url import UpdateUrlRequest

        # Empty request — nothing in model_fields_set, no long_url or alias given
        result = await svc.update(URL_OID, UpdateUrlRequest(), USER_OID)

        url_repo.update.assert_not_awaited()
        url_cache.invalidate.assert_not_awaited()
        assert result is existing

    @pytest.mark.asyncio
    async def test_update_clears_password_when_set_to_none(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc(password="oldhash")
        url_repo.find_by_id.return_value = existing
        url_repo.update.return_value = True
        url_cache.invalidate.return_value = None

        from schemas.dto.requests.url import UpdateUrlRequest

        req = UpdateUrlRequest(password=None)
        # Pydantic v2: explicitly passing password=None puts it in model_fields_set
        assert "password" in req.model_fields_set

        await svc.update(URL_OID, req, USER_OID)

        call_args = url_repo.update.call_args[0][1]
        assert call_args["$set"]["password"] is None

    @pytest.mark.asyncio
    async def test_update_clears_max_clicks_when_set_to_zero(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc(max_clicks=100)
        url_repo.find_by_id.return_value = existing
        url_repo.update.return_value = True

        from schemas.dto.requests.url import UpdateUrlRequest

        req = UpdateUrlRequest(max_clicks=0)
        await svc.update(URL_OID, req, USER_OID)

        call_args = url_repo.update.call_args[0][1]
        assert call_args["$set"]["max_clicks"] is None

    @pytest.mark.asyncio
    async def test_update_clears_expire_after_when_set_to_none(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc(
            expire_after=datetime(2030, 1, 1, tzinfo=timezone.utc)
        )
        url_repo.find_by_id.return_value = existing
        url_repo.update.return_value = True

        from schemas.dto.requests.url import UpdateUrlRequest

        req = UpdateUrlRequest(expire_after=None)
        await svc.update(URL_OID, req, USER_OID)

        call_args = url_repo.update.call_args[0][1]
        assert call_args["$set"]["expire_after"] is None

    @pytest.mark.asyncio
    async def test_update_alias_conflict_raises(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc(alias="old123")
        url_repo.find_by_id.return_value = existing
        # alias is taken
        url_repo.check_alias_exists.return_value = True
        legacy_repo.check_exists.return_value = False

        from schemas.dto.requests.url import UpdateUrlRequest

        req = UpdateUrlRequest(alias="newcode")
        with pytest.raises(ConflictError):
            await svc.update(URL_OID, req, USER_OID)

    @pytest.mark.asyncio
    async def test_update_changes_block_bots(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        existing = make_url_v2_doc(block_bots=False)
        url_repo.find_by_id.return_value = existing
        url_repo.update.return_value = True

        from schemas.dto.requests.url import UpdateUrlRequest

        req = UpdateUrlRequest(block_bots=True)
        await svc.update(URL_OID, req, USER_OID)

        call_args = url_repo.update.call_args[0][1]
        assert call_args["$set"]["block_bots"] is True


# ─────────────────────────────────────────────────────────────────────────────
# TestUrlServiceListByOwner
# ─────────────────────────────────────────────────────────────────────────────


class TestUrlServiceListByOwner:
    @pytest.mark.asyncio
    async def test_list_no_filter_returns_pagination(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_repo.count_by_query.return_value = 1
        url_repo.find_by_owner.return_value = [make_url_v2_doc()]

        from schemas.dto.requests.url import ListUrlsQuery

        result = await svc.list_by_owner(USER_OID, ListUrlsQuery())

        assert result["total"] == 1
        assert result["page"] == 1
        assert len(result["items"]) == 1
        assert result["hasNext"] is False

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_repo.count_by_query.return_value = 0
        url_repo.find_by_owner.return_value = []

        from schemas.dto.requests.url import ListUrlsQuery

        q = ListUrlsQuery(filter='{"status": "INACTIVE"}')
        await svc.list_by_owner(USER_OID, q)

        call_query = url_repo.count_by_query.call_args[0][0]
        assert call_query.get("status") == "INACTIVE"

    @pytest.mark.asyncio
    async def test_list_with_search_filter(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_repo.count_by_query.return_value = 0
        url_repo.find_by_owner.return_value = []

        from schemas.dto.requests.url import ListUrlsQuery

        q = ListUrlsQuery(filter='{"search": "example"}')
        await svc.list_by_owner(USER_OID, q)

        call_query = url_repo.count_by_query.call_args[0][0]
        assert "$or" in call_query

    @pytest.mark.asyncio
    async def test_list_with_password_set_filter(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_repo.count_by_query.return_value = 0
        url_repo.find_by_owner.return_value = []

        from schemas.dto.requests.url import ListUrlsQuery

        q = ListUrlsQuery(filter='{"passwordSet": true}')
        await svc.list_by_owner(USER_OID, q)

        call_query = url_repo.count_by_query.call_args[0][0]
        assert call_query.get("password") == {"$ne": None}

    @pytest.mark.asyncio
    async def test_list_with_max_clicks_set_false_filter(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_repo.count_by_query.return_value = 0
        url_repo.find_by_owner.return_value = []

        from schemas.dto.requests.url import ListUrlsQuery

        q = ListUrlsQuery(filter='{"maxClicksSet": false}')
        await svc.list_by_owner(USER_OID, q)

        call_query = url_repo.count_by_query.call_args[0][0]
        assert call_query.get("max_clicks") is None

    @pytest.mark.asyncio
    async def test_list_has_next_when_more_pages(self):
        url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache = make_repos()
        svc = make_service(
            url_repo, legacy_repo, emoji_repo, blocked_url_repo, url_cache
        )

        url_repo.count_by_query.return_value = 50
        url_repo.find_by_owner.return_value = [make_url_v2_doc()] * 20

        from schemas.dto.requests.url import ListUrlsQuery

        result = await svc.list_by_owner(USER_OID, ListUrlsQuery(pageSize=20))

        assert result["hasNext"] is True
        assert result["total"] == 50
