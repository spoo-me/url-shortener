"""
User document model.

Maps to the `users` MongoDB collection.

Two creation paths produce slightly different shapes:
- Password registration: no last_login_at, pfp is None
- OAuth registration: last_login_at set, pfp may be populated

Both paths are handled via Optional fields with sensible defaults.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from schemas.models.base import MongoBaseModel, PyObjectId


class ProviderProfile(BaseModel):
    """Nested profile data stored per OAuth provider."""

    name: Optional[str] = None
    picture: Optional[str] = None


class AuthProviderEntry(BaseModel):
    """Single entry in the user's auth_providers array."""

    provider: str
    provider_user_id: str
    email: Optional[str] = None
    email_verified: bool = False
    profile: ProviderProfile = ProviderProfile()
    linked_at: Optional[datetime] = None


class ProfilePicture(BaseModel):
    """Embedded profile picture sub-document."""

    url: str
    source: str
    last_updated: Optional[datetime] = None


class UserDoc(MongoBaseModel):
    """
    Document model for the `users` collection.

    status values: ACTIVE (only value currently in use)
    plan values: "free" (only value currently in use)
    """

    email: str
    email_verified: bool = False
    password_hash: Optional[str] = None
    password_set: bool = False
    user_name: Optional[str] = None
    pfp: Optional[ProfilePicture] = None
    auth_providers: list[AuthProviderEntry] = []
    plan: str = "free"
    signup_ip: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    status: str = "ACTIVE"
