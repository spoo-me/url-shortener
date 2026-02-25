"""Unit tests for MongoDB document models (Phase 2)."""

from datetime import datetime, timezone

import pytest
from bson import ObjectId

from schemas.models.base import ANONYMOUS_OWNER_ID, MongoBaseModel, PyObjectId
from schemas.models.url import EmojiUrlDoc, LegacyUrlDoc, UrlV2Doc
from schemas.models.user import AuthProviderEntry, ProfilePicture, UserDoc
from schemas.models.click import ClickDoc, ClickMeta
from schemas.models.api_key import ApiKeyDoc
from schemas.models.token import VerificationTokenDoc


# ── Helpers ───────────────────────────────────────────────────────────────────

def now():
    return datetime.now(timezone.utc)


def oid():
    return ObjectId()


# ── PyObjectId ────────────────────────────────────────────────────────────────

class TestPyObjectId:
    def test_accepts_objectid_instance(self):
        o = oid()
        assert PyObjectId._validate(o) == o

    def test_accepts_valid_string(self):
        s = str(oid())
        result = PyObjectId._validate(s)
        assert isinstance(result, ObjectId)
        assert str(result) == s

    def test_rejects_invalid_string(self):
        with pytest.raises(ValueError):
            PyObjectId._validate("not-an-objectid")

    def test_rejects_none(self):
        with pytest.raises((ValueError, TypeError)):
            PyObjectId._validate(None)


# ── MongoBaseModel ─────────────────────────────────────────────────────────────

class TestMongoBaseModel:
    def test_from_mongo_returns_none_for_none(self):
        assert MongoBaseModel.from_mongo(None) is None

    def test_id_alias(self):
        o = oid()
        m = MongoBaseModel.model_validate({"_id": o})
        assert m.id == o

    def test_to_mongo_drops_none_id(self):
        m = MongoBaseModel()
        d = m.to_mongo()
        assert "_id" not in d

    def test_to_mongo_keeps_set_id(self):
        o = oid()
        m = MongoBaseModel.model_validate({"_id": o})
        d = m.to_mongo()
        assert d["_id"] == o


# ── UrlV2Doc ──────────────────────────────────────────────────────────────────

class TestUrlV2Doc:
    def _make(self, **overrides):
        base = {
            "_id": oid(),
            "alias": "abc1234",
            "owner_id": oid(),
            "created_at": now(),
            "long_url": "https://example.com",
        }
        base.update(overrides)
        return UrlV2Doc.model_validate(base)

    def test_instantiation(self):
        doc = self._make()
        assert doc.alias == "abc1234"
        assert doc.status == "ACTIVE"
        assert doc.total_clicks == 0
        assert doc.private_stats is True

    def test_optional_fields_default_none(self):
        doc = self._make()
        assert doc.password is None
        assert doc.max_clicks is None
        assert doc.last_click is None
        assert doc.expire_after is None

    def test_to_mongo_round_trip(self):
        o = oid()
        owner = oid()
        t = now()
        doc = self._make(**{"_id": o, "owner_id": owner, "created_at": t, "max_clicks": 10})
        mongo = doc.to_mongo()
        restored = UrlV2Doc.from_mongo(mongo)
        assert restored.alias == doc.alias
        assert restored.max_clicks == 10
        assert str(restored.id) == str(o)

    def test_from_mongo_none_returns_none(self):
        assert UrlV2Doc.from_mongo(None) is None


# ── LegacyUrlDoc ─────────────────────────────────────────────────────────────

class TestLegacyUrlDoc:
    def _make(self, **overrides):
        base = {
            "_id": "abcdef",
            "url": "https://example.com",
        }
        base.update(overrides)
        return LegacyUrlDoc.model_validate(base)

    def test_string_id(self):
        doc = self._make()
        assert doc.id == "abcdef"

    def test_hyphenated_aliases(self):
        doc = LegacyUrlDoc.model_validate({
            "_id": "abcdef",
            "url": "https://example.com",
            "max-clicks": 100,
            "total-clicks": 5,
            "block-bots": True,
            "last-click": "2024-01-01 12:00:00",
            "last-click-browser": "Chrome",
            "last-click-os": "Windows",
            "last-click-country": "US",
        })
        assert doc.max_clicks == 100
        assert doc.total_clicks == 5
        assert doc.block_bots is True
        assert doc.last_click_browser == "Chrome"

    def test_to_mongo_uses_hyphenated_keys(self):
        doc = LegacyUrlDoc.model_validate({
            "_id": "abcdef",
            "url": "https://example.com",
            "max-clicks": 50,
            "total-clicks": 3,
        })
        mongo = doc.to_mongo()
        assert "max-clicks" in mongo
        assert "total-clicks" in mongo
        assert mongo["max-clicks"] == 50

    def test_missing_optional_fields_use_defaults(self):
        doc = self._make()
        assert doc.max_clicks is None
        assert doc.total_clicks == 0
        assert doc.block_bots is None
        assert doc.ips == []
        assert doc.counter == {}

    def test_from_mongo_none_returns_none(self):
        assert LegacyUrlDoc.from_mongo(None) is None


# ── EmojiUrlDoc ───────────────────────────────────────────────────────────────

class TestEmojiUrlDoc:
    def test_same_shape_as_legacy(self):
        doc = EmojiUrlDoc.model_validate({
            "_id": "🚀🎉",
            "url": "https://example.com",
            "max-clicks": 5,
        })
        assert doc.id == "🚀🎉"
        assert doc.max_clicks == 5


# ── UserDoc ────────────────────────────────────────────────────────────────────

class TestUserDoc:
    def _make(self, **overrides):
        base = {
            "_id": oid(),
            "email": "user@example.com",
        }
        base.update(overrides)
        return UserDoc.model_validate(base)

    def test_minimal_instantiation(self):
        doc = self._make()
        assert doc.email == "user@example.com"
        assert doc.email_verified is False
        assert doc.password_set is False
        assert doc.plan == "free"
        assert doc.status == "ACTIVE"
        assert doc.auth_providers == []

    def test_password_user_shape(self):
        doc = self._make(
            password_hash="$argon2id$...",
            password_set=True,
            email_verified=False,
        )
        assert doc.password_hash == "$argon2id$..."
        assert doc.password_set is True

    def test_oauth_user_shape(self):
        t = now()
        doc = self._make(
            password_hash=None,
            password_set=False,
            email_verified=True,
            pfp={"url": "https://example.com/pic.jpg", "source": "google", "last_updated": t},
            auth_providers=[{
                "provider": "google",
                "provider_user_id": "123",
                "email": "user@example.com",
                "email_verified": True,
                "profile": {"name": "Alice", "picture": "https://example.com/pic.jpg"},
                "linked_at": t,
            }],
        )
        assert doc.pfp.source == "google"
        assert len(doc.auth_providers) == 1
        assert doc.auth_providers[0].provider == "google"

    def test_pfp_none(self):
        doc = self._make(pfp=None)
        assert doc.pfp is None

    def test_from_mongo_round_trip(self):
        o = oid()
        t = now()
        doc = self._make(**{"_id": o, "created_at": t, "updated_at": t})
        restored = UserDoc.from_mongo(doc.to_mongo())
        assert restored.email == doc.email
        assert str(restored.id) == str(o)


# ── ClickDoc ──────────────────────────────────────────────────────────────────

class TestClickDoc:
    def _make(self, **overrides):
        url_id = oid()
        base = {
            "clicked_at": now(),
            "meta": {
                "url_id": url_id,
                "short_code": "abc1234",
                "owner_id": oid(),
            },
            "ip_address": "1.2.3.4",
            "browser": "Chrome",
            "os": "Windows",
            "redirect_ms": 42,
        }
        base.update(overrides)
        return ClickDoc.model_validate(base)

    def test_instantiation(self):
        doc = self._make()
        assert doc.country == "Unknown"
        assert doc.city == "Unknown"
        assert doc.referrer is None
        assert doc.bot_name is None

    def test_meta_subdocument(self):
        doc = self._make()
        assert isinstance(doc.meta.url_id, ObjectId)
        assert doc.meta.short_code == "abc1234"

    def test_anonymous_owner_id(self):
        doc = self._make(**{"meta": {
            "url_id": oid(),
            "short_code": "abc1234",
            "owner_id": ANONYMOUS_OWNER_ID,
        }})
        assert doc.meta.owner_id == ANONYMOUS_OWNER_ID

    def test_to_mongo_round_trip(self):
        doc = self._make(referrer="google.com", bot_name=None)
        mongo = doc.to_mongo()
        restored = ClickDoc.from_mongo(mongo)
        assert restored.referrer == "google.com"
        assert restored.redirect_ms == doc.redirect_ms


# ── ApiKeyDoc ─────────────────────────────────────────────────────────────────

class TestApiKeyDoc:
    def _make(self, **overrides):
        base = {
            "_id": oid(),
            "user_id": oid(),
            "token_prefix": "AbCdEfGh",
            "token_hash": "abc123" * 10,
            "name": "My Key",
            "scopes": ["shorten:create"],
            "created_at": now(),
        }
        base.update(overrides)
        return ApiKeyDoc.model_validate(base)

    def test_instantiation(self):
        doc = self._make()
        assert doc.name == "My Key"
        assert doc.revoked is False
        assert doc.description is None
        assert doc.expires_at is None

    def test_to_mongo_round_trip(self):
        doc = self._make(description="test key")
        restored = ApiKeyDoc.from_mongo(doc.to_mongo())
        assert restored.description == "test key"
        assert restored.scopes == ["shorten:create"]


# ── VerificationTokenDoc ───────────────────────────────────────────────────────

class TestVerificationTokenDoc:
    def _make(self, **overrides):
        base = {
            "_id": oid(),
            "user_id": oid(),
            "email": "user@example.com",
            "token_hash": "deadbeef" * 8,
            "token_type": "email_verify",
            "expires_at": now(),
            "created_at": now(),
        }
        base.update(overrides)
        return VerificationTokenDoc.model_validate(base)

    def test_instantiation(self):
        doc = self._make()
        assert doc.used_at is None
        assert doc.attempts == 0

    def test_attempts_non_negative(self):
        with pytest.raises(Exception):
            self._make(attempts=-1)

    def test_to_mongo_round_trip(self):
        t = now()
        doc = self._make(used_at=t)
        restored = VerificationTokenDoc.from_mongo(doc.to_mongo())
        assert restored.token_type == "email_verify"
        assert restored.used_at == t
