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
from typing import Optional

from pydantic import Field

from schemas.models.base import MongoBaseModel, PyObjectId


TOKEN_TYPE_EMAIL_VERIFY = "email_verify"
TOKEN_TYPE_PASSWORD_RESET = "password_reset"


class VerificationTokenDoc(MongoBaseModel):
    """Document model for the `verification-tokens` collection."""

    user_id: PyObjectId
    email: str
    token_hash: str
    token_type: str
    expires_at: datetime
    created_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
    attempts: int = Field(default=0, ge=0)
