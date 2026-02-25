"""
API key document model.

Maps to the `api-keys` MongoDB collection.

token_hash stores SHA-256(raw_token) — the raw token is shown once at creation
and never stored. token_prefix (first 8 chars) is stored for display purposes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from schemas.models.base import MongoBaseModel, PyObjectId


class ApiKeyDoc(MongoBaseModel):
    """Document model for the `api-keys` collection."""

    user_id: PyObjectId
    token_prefix: str
    token_hash: str
    name: str
    description: Optional[str] = None
    scopes: list[str] = []
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    revoked: bool = False
