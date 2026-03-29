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

from pydantic import BaseModel

from schemas.models.base import MongoBaseModel


class ProviderProfile(BaseModel):
    """Nested profile data stored per OAuth provider."""

    name: str | None = None
    picture: str | None = None


class AuthProviderEntry(BaseModel):
    """Single entry in the user's auth_providers array."""

    provider: str
    provider_user_id: str
    email: str | None = None
    email_verified: bool = False
    profile: ProviderProfile = ProviderProfile()
    linked_at: datetime | None = None


class ProfilePicture(BaseModel):
    """Embedded profile picture sub-document."""

    url: str
    source: str
    last_updated: datetime | None = None


class UserDoc(MongoBaseModel):
    """
    Document model for the `users` collection.

    status values: ACTIVE (only value currently in use)
    plan values: "free" (only value currently in use)
    """

    email: str
    email_verified: bool = False
    password_hash: str | None = None
    password_set: bool = False
    user_name: str | None = None
    pfp: ProfilePicture | None = None
    auth_providers: list[AuthProviderEntry] = []  # noqa: RUF012
    plan: str = "free"
    signup_ip: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None
    status: str = "ACTIVE"
