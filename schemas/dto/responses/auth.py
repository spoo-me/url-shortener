"""
Response DTOs for authentication endpoints.

AuthProviderInfo    — auth provider entry in UserProfileResponse
UserPfp             — profile picture in UserProfileResponse
UserProfileResponse — shape returned by get_user_profile() helper
LoginResponse       — POST /auth/login  (200)
RegisterResponse    — POST /auth/register  (201)
RefreshResponse     — POST /auth/refresh  (200)
LogoutResponse      — POST /auth/logout  (200)
VerifyEmailResponse — POST /auth/verify-email  (200)
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuthProviderInfo(BaseModel):
    """Minimal OAuth provider entry returned inside UserProfileResponse."""

    model_config = ConfigDict(populate_by_name=True)

    provider: Optional[str] = None
    email: Optional[str] = None
    linked_at: Optional[str] = None  # ISO 8601 string


class UserPfp(BaseModel):
    """Profile picture info returned inside UserProfileResponse."""

    model_config = ConfigDict(populate_by_name=True)

    url: Optional[str] = None
    source: Optional[str] = None


class UserProfileResponse(BaseModel):
    """User profile shape returned by get_user_profile() — used in login/register/me."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    email: Optional[str] = None
    email_verified: bool
    user_name: Optional[str] = None
    plan: str
    password_set: bool
    auth_providers: list[AuthProviderInfo]
    # pfp is absent from the JSON when None (route handlers use exclude_none=True)
    pfp: Optional[UserPfp] = None


class LoginResponse(BaseModel):
    """Response body for POST /auth/login (200)."""

    model_config = ConfigDict(populate_by_name=True)

    access_token: str
    user: UserProfileResponse


class RegisterResponse(BaseModel):
    """Response body for POST /auth/register (201)."""

    model_config = ConfigDict(populate_by_name=True)

    access_token: str
    user: UserProfileResponse
    requires_verification: bool
    verification_sent: bool


class RefreshResponse(BaseModel):
    """Response body for POST /auth/refresh (200)."""

    model_config = ConfigDict(populate_by_name=True)

    access_token: str


class LogoutResponse(BaseModel):
    """Response body for POST /auth/logout (200)."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool


class VerifyEmailResponse(BaseModel):
    """Response body for POST /auth/verify-email (200)."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    message: str
    email_verified: bool
