"""
URL document models.

Three separate schemas map to three MongoDB collections:

  UrlV2Doc     → urlsV2     (current schema, ObjectId _id, separate alias field)
  LegacyUrlDoc → urls       (v1 schema, short_code is _id, hyphenated field names,
                              embedded analytics, plaintext password)
  EmojiUrlDoc  → emojis     (same structure as LegacyUrlDoc)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from pydantic import ConfigDict, Field

from schemas.models.base import MongoBaseModel, PyObjectId


class UrlV2Doc(MongoBaseModel):
    """
    Document model for the `urlsV2` collection.

    Status values: ACTIVE | INACTIVE | EXPIRED | BLOCKED
    password stores an argon2 hash (None when no password set).
    owner_id is ANONYMOUS_OWNER_ID sentinel for unowned URLs.
    """

    alias: str
    owner_id: PyObjectId
    created_at: datetime
    creation_ip: Optional[str] = None
    long_url: str
    password: Optional[str] = None
    block_bots: Optional[bool] = None
    max_clicks: Optional[int] = None
    expire_after: Optional[datetime] = None
    status: str = "ACTIVE"
    private_stats: bool = True
    total_clicks: int = 0
    last_click: Optional[datetime] = None


class LegacyUrlDoc(MongoBaseModel):
    """
    Document model for the `urls` collection (v1 schema).

    Key differences from v2:
    - `_id` IS the short code string (not an ObjectId).
    - Field names use hyphens: `max-clicks`, `total-clicks`, `block-bots`, etc.
      Pydantic field aliases map these to valid Python identifiers.
    - Analytics are embedded directly on the URL document.
    - Password is stored in plaintext.
    - No owner_id, no status field.

    Note: `id` inherited from MongoBaseModel is typed as Optional[PyObjectId],
    but for v1 documents it holds a plain string. We override it here with
    Optional[Any] and rely on from_mongo() to pass through whatever _id value
    MongoDB returns. Repositories never interpret this field as an ObjectId.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    # _id is the short code string for v1 — override base type
    id: Optional[Any] = Field(default=None, alias="_id")

    url: str
    password: Optional[str] = None

    # Hyphenated field names — use aliases matching exact MongoDB keys
    max_clicks: Optional[int] = Field(default=None, alias="max-clicks")
    total_clicks: int = Field(default=0, alias="total-clicks")
    block_bots: Optional[bool] = Field(default=None, alias="block-bots")
    expiration_time: Optional[datetime] = Field(default=None, alias="expiration-time")
    last_click: Optional[str] = Field(default=None, alias="last-click")
    last_click_browser: Optional[str] = Field(default=None, alias="last-click-browser")
    last_click_os: Optional[str] = Field(default=None, alias="last-click-os")
    last_click_country: Optional[str] = Field(default=None, alias="last-click-country")

    # Embedded analytics (dynamic dict fields — not typed further to preserve
    # the arbitrary key structure used for country/browser/os/referrer tracking)
    ips: list[str] = Field(default_factory=list)
    counter: dict[str, int] = Field(default_factory=dict)
    unique_counter: dict[str, int] = Field(default_factory=dict)
    country: dict[str, Any] = Field(default_factory=dict)
    browser: dict[str, Any] = Field(default_factory=dict)
    os_name: dict[str, Any] = Field(default_factory=dict)
    referrer: dict[str, Any] = Field(default_factory=dict)
    bots: dict[str, int] = Field(default_factory=dict)
    average_redirection_time: float = 0.0


class EmojiUrlDoc(LegacyUrlDoc):
    """
    Document model for the `emojis` collection.

    Identical structure to LegacyUrlDoc — the only difference is which
    MongoDB collection it lives in. Repositories use the correct collection.
    """
