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
from enum import Enum

from pydantic import BaseModel

from schemas.models.base import MongoBaseModel


class UserStatus(str, Enum):
    """Status values for user accounts."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class OAuthAction(str, Enum):
    """OAuth flow action types."""

    LOGIN = "login"
    LINK = "link"


class UserPlan(str, Enum):
    """User subscription plans."""

    FREE = "free"


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""

    GOOGLE = "google"
    GITHUB = "github"
    DISCORD = "discord"


class ProviderInfo(BaseModel):
    """Normalised user-info returned by OAuth provider strategies.

    All three providers (Google, GitHub, Discord) produce the same shape.
    Pydantic will coerce a plain dict into this model automatically.
    """

    provider_user_id: str
    email: str
    email_verified: bool = False
    name: str | None = None
    picture: str | None = None
    given_name: str | None = None
    family_name: str | None = None


class ProviderProfile(BaseModel):
    """Nested profile data stored per OAuth provider."""

    name: str | None = None
    picture: str | None = None


class AuthProviderEntry(BaseModel):
    """Single entry in the user's auth_providers array."""

    provider: OAuthProvider
    provider_user_id: str
    email: str | None = None
    email_verified: bool = False
    profile: ProviderProfile = ProviderProfile()
    linked_at: datetime | None = None


class ProfilePicture(BaseModel):
    """Embedded profile picture sub-document."""

    url: str
    source: OAuthProvider
    last_updated: datetime | None = None


class UserDoc(MongoBaseModel):
    """
    Document model for the `users` collection.

    status: UserStatus enum (ACTIVE, INACTIVE)
    plan: UserPlan enum (FREE)
    """

    email: str
    email_verified: bool = False
    password_hash: str | None = None
    password_set: bool = False
    user_name: str | None = None
    pfp: ProfilePicture | None = None
    auth_providers: list[AuthProviderEntry] = []  # noqa: RUF012
    plan: UserPlan = UserPlan.FREE
    signup_ip: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None
    status: UserStatus = UserStatus.ACTIVE
