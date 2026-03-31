"""
Verification token document model.

Maps to the `verification-tokens` MongoDB collection.

Used for both email verification OTPs and password reset OTPs.
token_hash stores SHA-256(otp_code) — the plain OTP is never stored.
used_at is None until the token is consumed.
attempts tracks failed verification tries (max 5 before the token is dead).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field

from schemas.models.base import MongoBaseModel, PyObjectId


class TokenType(str, Enum):
    """Verification token types."""

    EMAIL_VERIFY = "email_verify"
    PASSWORD_RESET = "password_reset"
    DEVICE_AUTH = "extension_auth"


# Backward-compat aliases for existing imports
TOKEN_TYPE_EMAIL_VERIFY = TokenType.EMAIL_VERIFY
TOKEN_TYPE_PASSWORD_RESET = TokenType.PASSWORD_RESET
TOKEN_TYPE_DEVICE_AUTH = TokenType.DEVICE_AUTH


class VerificationTokenDoc(MongoBaseModel):
    """Document model for the `verification-tokens` collection."""

    user_id: PyObjectId
    email: str
    token_hash: str
    token_type: TokenType
    expires_at: datetime
    created_at: datetime | None = None
    used_at: datetime | None = None
    attempts: int = Field(default=0, ge=0)
