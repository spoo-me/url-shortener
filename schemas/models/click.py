"""
Click document model.

Maps to the `clicks` MongoDB time-series collection.

Time-series schema:
  timeField  = "clicked_at"
  metaField  = "meta"
  granularity = "seconds"

The `meta` subdocument groups clicks by URL for efficient range queries.
owner_id always holds an ObjectId — anonymous clicks use ANONYMOUS_OWNER_ID
to avoid bucket churn from mixed None/ObjectId types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from schemas.models.base import MongoBaseModel, PyObjectId


class ClickMeta(BaseModel):
    """The metaField subdocument for the time-series collection."""

    url_id: PyObjectId
    short_code: str
    owner_id: PyObjectId  # ANONYMOUS_OWNER_ID for unowned URLs


class ClickDoc(MongoBaseModel):
    """Document model for the `clicks` time-series collection."""

    # Time-series timeField
    clicked_at: datetime

    # Time-series metaField
    meta: ClickMeta

    # Analytics fields
    ip_address: str
    country: str = "Unknown"
    city: str = "Unknown"
    browser: str
    os: str
    redirect_ms: int
    referrer: Optional[str] = None  # sanitised referrer domain, nullable
    bot_name: Optional[str] = None  # nullable
