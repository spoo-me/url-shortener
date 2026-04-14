"""Unit tests for URL request and response DTOs."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from pydantic import ValidationError

from schemas.dto.requests.url import (
    CreateUrlRequest,
    ListUrlsQuery,
    UpdateUrlRequest,
)
from schemas.dto.responses.url import (
    UpdateUrlResponse,
    UrlListItem,
    UrlListResponse,
    UrlResponse,
)
from schemas.models.url import UrlV2Doc

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

    def test_invalid_sort_by_rejected(self):
        with pytest.raises(ValidationError):
            ListUrlsQuery.model_validate({"sortBy": "invalid_field"})

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


# ── Response DTO serialization shapes ─────────────────────────────────────────


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


# ── from_doc() factory method tests ──────────────────────────────────────────


def _make_doc(**overrides) -> UrlV2Doc:
    """Build a UrlV2Doc with sensible defaults; override via kwargs."""
    base = {
        "_id": ObjectId(),
        "alias": "test123",
        "owner_id": ObjectId(),
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "long_url": "https://example.com/long",
        "password": None,
        "block_bots": False,
        "max_clicks": None,
        "expire_after": None,
        "status": "ACTIVE",
        "private_stats": False,
        "total_clicks": 42,
        "last_click": datetime(2025, 6, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 3, 1, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return UrlV2Doc.from_mongo(base)


class TestUrlResponseFromDoc:
    def test_basic_fields(self):
        doc = _make_doc()
        r = UrlResponse.from_doc(doc, "https://spoo.me")
        assert r.alias == "test123"
        assert r.short_url == "https://spoo.me/test123"
        assert r.long_url == "https://example.com/long"
        assert r.status == "ACTIVE"

    def test_owner_id_stringified(self):
        oid = ObjectId()
        r = UrlResponse.from_doc(_make_doc(owner_id=oid), "https://spoo.me")
        assert r.owner_id == str(oid)

    def test_anonymous_owner_id_returns_none(self):
        """Anonymous URLs (sentinel ObjectId) should return null owner_id."""
        from schemas.models.base import ANONYMOUS_OWNER_ID

        r = UrlResponse.from_doc(
            _make_doc(owner_id=ANONYMOUS_OWNER_ID), "https://spoo.me"
        )
        assert r.owner_id is None

    def test_created_at_is_unix_timestamp(self):
        r = UrlResponse.from_doc(_make_doc(), "https://spoo.me")
        assert isinstance(r.created_at, int)
        assert r.created_at == int(
            datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
        )

    def test_app_url_trailing_slash_stripped(self):
        r = UrlResponse.from_doc(_make_doc(), "https://spoo.me/")
        assert r.short_url == "https://spoo.me/test123"


class TestUpdateUrlResponseFromDoc:
    def test_basic_fields(self):
        doc = _make_doc()
        r = UpdateUrlResponse.from_doc(doc)
        assert r.id == str(doc.id)
        assert r.alias == "test123"
        assert r.long_url == "https://example.com/long"
        assert r.status == "ACTIVE"

    def test_password_set_true_when_password_exists(self):
        r = UpdateUrlResponse.from_doc(_make_doc(password="$argon2id$hash"))
        assert r.password_set is True

    def test_password_set_false_when_no_password(self):
        r = UpdateUrlResponse.from_doc(_make_doc(password=None))
        assert r.password_set is False

    def test_max_clicks_preserved(self):
        r = UpdateUrlResponse.from_doc(_make_doc(max_clicks=100))
        assert r.max_clicks == 100

    def test_max_clicks_none(self):
        r = UpdateUrlResponse.from_doc(_make_doc(max_clicks=None))
        assert r.max_clicks is None

    def test_expire_after_as_unix_timestamp(self):
        dt = datetime(2025, 12, 31, tzinfo=timezone.utc)
        r = UpdateUrlResponse.from_doc(_make_doc(expire_after=dt))
        assert r.expire_after == int(dt.timestamp())

    def test_expire_after_none(self):
        r = UpdateUrlResponse.from_doc(_make_doc(expire_after=None))
        assert r.expire_after is None

    def test_updated_at_as_unix_timestamp(self):
        r = UpdateUrlResponse.from_doc(_make_doc())
        assert isinstance(r.updated_at, int)

    def test_updated_at_none_defaults_to_zero(self):
        r = UpdateUrlResponse.from_doc(_make_doc(updated_at=None))
        assert r.updated_at == 0


class TestUrlListItemFromDoc:
    def test_basic_fields(self):
        doc = _make_doc()
        r = UrlListItem.from_doc(doc)
        assert r.id == str(doc.id)
        assert r.alias == "test123"
        assert r.total_clicks == 42

    def test_password_set_derived(self):
        assert UrlListItem.from_doc(_make_doc(password="hash")).password_set is True
        assert UrlListItem.from_doc(_make_doc(password=None)).password_set is False

    def test_block_bots_none_preserved(self):
        r = UrlListItem.from_doc(_make_doc(block_bots=None))
        assert r.block_bots is None

    def test_block_bots_false_preserved(self):
        r = UrlListItem.from_doc(_make_doc(block_bots=False))
        assert r.block_bots is False

    def test_block_bots_true(self):
        r = UrlListItem.from_doc(_make_doc(block_bots=True))
        assert r.block_bots is True

    def test_created_at_is_utc_datetime(self):
        r = UrlListItem.from_doc(_make_doc())
        assert r.created_at is not None
        assert r.created_at.tzinfo is not None

    def test_created_at_naive_gets_utc(self):
        naive = datetime(2025, 1, 1)  # no tzinfo
        r = UrlListItem.from_doc(_make_doc(created_at=naive))
        assert r.created_at.tzinfo == timezone.utc

    def test_last_click_none(self):
        r = UrlListItem.from_doc(_make_doc(last_click=None))
        assert r.last_click is None

    def test_last_click_utc(self):
        r = UrlListItem.from_doc(_make_doc())
        assert r.last_click is not None
        assert r.last_click.tzinfo is not None

    def test_expire_after_as_unix_timestamp(self):
        dt = datetime(2025, 12, 31, tzinfo=timezone.utc)
        r = UrlListItem.from_doc(_make_doc(expire_after=dt))
        assert r.expire_after == int(dt.timestamp())

    def test_expire_after_none(self):
        r = UrlListItem.from_doc(_make_doc(expire_after=None))
        assert r.expire_after is None
