"""
Request DTOs for authentication endpoints.

LoginRequest                  — POST /auth/login
RegisterRequest               — POST /auth/register
SetPasswordRequest            — POST /auth/set-password
VerifyEmailRequest            — POST /auth/verify-email
SendVerificationRequest       — POST /auth/send-verification  (no body)
RequestPasswordResetRequest   — POST /auth/request-password-reset
ResetPasswordRequest          — POST /auth/reset-password
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""

    model_config = ConfigDict(populate_by_name=True)

    email: str
    password: str


class RegisterRequest(BaseModel):
    """Request body for POST /auth/register."""

    model_config = ConfigDict(populate_by_name=True)

    email: str
    password: str
    user_name: str | None = None


class SetPasswordRequest(BaseModel):
    """Request body for POST /auth/set-password.

    Only applies to OAuth-only users who have not yet set a password.
    """

    model_config = ConfigDict(populate_by_name=True)

    password: str


class VerifyEmailRequest(BaseModel):
    """Request body for POST /auth/verify-email.

    ``code`` is the 6-digit OTP sent to the user's email address.
    """

    model_config = ConfigDict(populate_by_name=True)

    code: str


class RequestPasswordResetRequest(BaseModel):
    """Request body for POST /auth/request-password-reset."""

    model_config = ConfigDict(populate_by_name=True)

    email: str


class ResetPasswordRequest(BaseModel):
    """Request body for POST /auth/reset-password."""

    model_config = ConfigDict(populate_by_name=True)

    email: str
    code: str
    password: str
