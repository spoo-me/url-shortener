"""Unit tests for UrlV2Doc, LegacyUrlDoc, and EmojiUrlDoc."""

from schemas.models.url import EmojiUrlDoc, LegacyUrlDoc, UrlV2Doc

from .conftest import now, oid


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
        for field in ("password", "max_clicks", "last_click", "expire_after"):
            assert getattr(doc, field) is None, f"{field} should default to None"

    def test_to_mongo_round_trip(self):
        o, owner, t = oid(), oid(), now()
        doc = self._make(
            **{"_id": o, "owner_id": owner, "created_at": t, "max_clicks": 10}
        )
        restored = UrlV2Doc.from_mongo(doc.to_mongo())
        assert restored.alias == doc.alias
        assert restored.max_clicks == 10
        assert str(restored.id) == str(o)

    def test_from_mongo_none_returns_none(self):
        assert UrlV2Doc.from_mongo(None) is None


# ── LegacyUrlDoc ─────────────────────────────────────────────────────────────


class TestLegacyUrlDoc:
    def _make(self, **overrides):
        base = {"_id": "abcdef", "url": "https://example.com"}
        base.update(overrides)
        return LegacyUrlDoc.model_validate(base)

    def test_string_id(self):
        assert self._make().id == "abcdef"

    def test_hyphenated_aliases(self):
        doc = LegacyUrlDoc.model_validate(
            {
                "_id": "abcdef",
                "url": "https://example.com",
                "max-clicks": 100,
                "total-clicks": 5,
                "block-bots": True,
                "last-click": "2024-01-01 12:00:00",
                "last-click-browser": "Chrome",
                "last-click-os": "Windows",
                "last-click-country": "US",
            }
        )
        assert doc.max_clicks == 100
        assert doc.total_clicks == 5
        assert doc.block_bots is True
        assert doc.last_click_browser == "Chrome"

    def test_to_mongo_uses_hyphenated_keys(self):
        doc = self._make(**{"max-clicks": 50, "total-clicks": 3})
        mongo = doc.to_mongo()
        assert mongo.get("max-clicks") == 50
        assert "total-clicks" in mongo

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
        doc = EmojiUrlDoc.model_validate(
            {
                "_id": "\U0001f680\U0001f389",
                "url": "https://example.com",
                "max-clicks": 5,
            }
        )
        assert doc.id == "\U0001f680\U0001f389"
        assert doc.max_clicks == 5
