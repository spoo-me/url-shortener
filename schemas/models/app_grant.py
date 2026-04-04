"""
App grant document model.

Maps to the `app-grants` MongoDB collection.

Tracks which apps a user has authorized via the consent flow.
Soft-deleted on revoke (revoked_at is set instead of deleting the document).
"""

from __future__ import annotations

from datetime import datetime

from schemas.models.base import MongoBaseModel, PyObjectId


class AppGrantDoc(MongoBaseModel):
    """Document model for the `app-grants` collection."""

    user_id: PyObjectId
    app_id: str  # matches key in config/apps.yaml
    granted_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None  # soft delete
