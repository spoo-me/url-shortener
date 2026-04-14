"""
Request DTOs for authentication endpoints.

LoginRequest                  — POST /auth/login
RegisterRequest               — POST /auth/register
SetPasswordRequest            — POST /auth/set-password
VerifyEmailRequest            — POST /auth/verify-email
SendVerificationRequest       — POST /auth/send-verification  (no body)
RequestPasswordResetRequest   — POST /auth/request-password-reset
ResetPasswordRequest          — POST /auth/reset-password
DeviceTokenRequest            — POST /auth/device/token
DeviceRefreshRequest          — POST /auth/device/refresh
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""

    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr = Field(
        description="Account email address", examples=["user@example.com"]
    )
    password: str = Field(
        max_length=255,
        description="Account password",
        examples=["MySecurePass123!"],
    )


class RegisterRequest(BaseModel):
    """Request body for POST /auth/register."""

    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr = Field(
        description="Email address for the new account",
        examples=["newuser@example.com"],
    )
    password: str = Field(
        max_length=128,
        description="Password (min 8 chars, must contain letter + number + special char)",
        examples=["MySecurePass123!"],
    )
    user_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Display name (optional)",
        examples=["Jane Doe"],
    )


class SetPasswordRequest(BaseModel):
    """Request body for POST /auth/set-password.

    Only applies to OAuth-only users who have not yet set a password.
    """

    model_config = ConfigDict(populate_by_name=True)

    password: str = Field(
        max_length=128,
        description="New password (min 8 chars, must contain letter + number + special char)",
        examples=["MySecurePass123!"],
    )


class VerifyEmailRequest(BaseModel):
    """Request body for POST /auth/verify-email.

    ``code`` is the 6-digit OTP sent to the user's email address.
    """

    model_config = ConfigDict(populate_by_name=True)

    code: str = Field(
        pattern=r"^[0-9]{6}$",
        description="6-digit OTP from verification email",
        examples=["123456"],
    )


class RequestPasswordResetRequest(BaseModel):
    """Request body for POST /auth/request-password-reset."""

    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr = Field(
        description="Email address of the account to reset",
        examples=["user@example.com"],
    )


class ResetPasswordRequest(BaseModel):
    """Request body for POST /auth/reset-password."""

    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr = Field(
        description="Email address of the account",
        examples=["user@example.com"],
    )
    code: str = Field(
        pattern=r"^[0-9]{6}$",
        description="6-digit OTP from password reset email",
        examples=["123456"],
    )
    password: str = Field(
        max_length=128,
        description="New password (min 8 chars, must contain letter + number + special char)",
        examples=["NewSecurePass456!"],
    )


class DeviceTokenRequest(BaseModel):
    """Request body for POST /auth/device/token."""

    model_config = ConfigDict(populate_by_name=True)

    code: str = Field(
        min_length=1,
        max_length=128,
        description="One-time auth code from the device callback page",
    )


class DeviceRefreshRequest(BaseModel):
    """Request body for POST /auth/device/refresh."""

    model_config = ConfigDict(populate_by_name=True)

    refresh_token: str = Field(
        min_length=1,
        description="JWT refresh token issued by /auth/device/token",
    )
