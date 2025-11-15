"""
Utilities for email verification and password reset tokens/OTPs
"""

import secrets
import hashlib
import string
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
from bson import ObjectId

from utils.logger import get_logger
from utils.mongo_utils import (
    create_verification_token,
    get_verification_token,
    mark_token_as_used,
    delete_user_tokens,
    count_recent_tokens,
)

log = get_logger(__name__)

# Token types
TOKEN_TYPE_EMAIL_VERIFY = "email_verify"
TOKEN_TYPE_PASSWORD_RESET = "password_reset"

# Expiry times (in seconds)
OTP_EXPIRY_SECONDS = 600  # 10 minutes
TOKEN_EXPIRY_SECONDS = 900  # 15 minutes

# Rate limiting
MAX_TOKENS_PER_HOUR = 3
MAX_VERIFICATION_ATTEMPTS = 5


def generate_otp_code(length: int = 6) -> str:
    """
    Generate a random numeric OTP code

    Args:
        length: Length of the OTP (default 6)

    Returns:
        String of random digits
    """
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token

    Args:
        length: Length in bytes (default 32)

    Returns:
        URL-safe base64 encoded token
    """
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """
    Hash a token using SHA256

    Args:
        token: Plain token to hash

    Returns:
        Hex-encoded SHA256 hash
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_email_verification_otp(
    user_id: str, email: str
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Create an email verification OTP for a user

    Args:
        user_id: User's MongoDB ObjectId as string
        email: User's email address

    Returns:
        Tuple of (success, otp_code, error_message)
    """
    try:
        # Rate limiting check
        recent_count = count_recent_tokens(user_id, TOKEN_TYPE_EMAIL_VERIFY, 60)
        if recent_count >= MAX_TOKENS_PER_HOUR:
            log.warning(
                "verification_rate_limited",
                user_id=user_id,
                token_type=TOKEN_TYPE_EMAIL_VERIFY,
                count=recent_count,
            )
            return (
                False,
                None,
                "Too many verification attempts. Please try again later.",
            )

        # Generate OTP
        otp_code = generate_otp_code()
        otp_hash = hash_token(otp_code)

        # Calculate expiry
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=OTP_EXPIRY_SECONDS)

        # Create token document
        token_data = {
            "user_id": ObjectId(user_id),
            "email": email,
            "token_hash": otp_hash,
            "token_type": TOKEN_TYPE_EMAIL_VERIFY,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
            "used_at": None,
            "attempts": 0,
        }

        # Save to database
        token_id = create_verification_token(token_data)

        if not token_id:
            log.error("verification_token_creation_failed", user_id=user_id)
            return False, None, "Failed to create verification token"

        log.info(
            "verification_token_created",
            user_id=user_id,
            token_id=str(token_id),
            token_type=TOKEN_TYPE_EMAIL_VERIFY,
        )

        return True, otp_code, None

    except Exception as e:
        log.error(
            "verification_token_creation_error",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return False, None, "An error occurred while creating verification token"


def create_password_reset_otp(
    user_id: str, email: str
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Create a password reset OTP for a user

    Args:
        user_id: User's MongoDB ObjectId as string
        email: User's email address

    Returns:
        Tuple of (success, otp_code, error_message)
    """
    try:
        # Rate limiting check
        recent_count = count_recent_tokens(user_id, TOKEN_TYPE_PASSWORD_RESET, 60)
        if recent_count >= MAX_TOKENS_PER_HOUR:
            log.warning(
                "password_reset_rate_limited",
                user_id=user_id,
                token_type=TOKEN_TYPE_PASSWORD_RESET,
                count=recent_count,
            )
            return (
                False,
                None,
                "Too many password reset attempts. Please try again later.",
            )

        # Delete any existing password reset tokens for this user
        delete_user_tokens(user_id, TOKEN_TYPE_PASSWORD_RESET)

        # Generate OTP
        otp_code = generate_otp_code()
        otp_hash = hash_token(otp_code)

        # Calculate expiry
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=OTP_EXPIRY_SECONDS)

        # Create token document
        token_data = {
            "user_id": ObjectId(user_id),
            "email": email,
            "token_hash": otp_hash,
            "token_type": TOKEN_TYPE_PASSWORD_RESET,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
            "used_at": None,
            "attempts": 0,
        }

        # Save to database
        token_id = create_verification_token(token_data)

        if not token_id:
            log.error("password_reset_token_creation_failed", user_id=user_id)
            return False, None, "Failed to create password reset token"

        log.info(
            "password_reset_token_created",
            user_id=user_id,
            token_id=str(token_id),
            token_type=TOKEN_TYPE_PASSWORD_RESET,
        )

        return True, otp_code, None

    except Exception as e:
        log.error(
            "password_reset_token_creation_error",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return False, None, "An error occurred while creating password reset token"


def verify_otp(
    user_id: str, otp_code: str, token_type: str
) -> Tuple[bool, Optional[str]]:
    """
    Verify an OTP code for a user

    Args:
        user_id: User's MongoDB ObjectId as string
        otp_code: The OTP code to verify
        token_type: Type of token (email_verify or password_reset)

    Returns:
        Tuple of (success, error_message)
    """
    try:
        otp_hash = hash_token(otp_code)

        # Find the token
        token_doc = get_verification_token(otp_hash, token_type)

        if not token_doc:
            log.warning(
                "otp_verification_failed",
                user_id=user_id,
                reason="token_not_found",
                token_type=token_type,
            )
            return False, "Invalid or expired verification code"

        # Check if token belongs to the user
        if str(token_doc["user_id"]) != user_id:
            log.warning(
                "otp_verification_failed",
                user_id=user_id,
                reason="user_mismatch",
                token_type=token_type,
            )
            return False, "Invalid verification code"

        # Check if token is expired
        # Ensure both datetimes are timezone-aware for comparison
        expires_at = token_doc["expires_at"]
        if not expires_at.tzinfo:
            # If the stored datetime is naive, assume it's UTC
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= datetime.now(timezone.utc):
            log.warning(
                "otp_verification_failed",
                user_id=user_id,
                reason="expired",
                token_type=token_type,
            )
            return False, "Verification code has expired"

        # Check if already used
        if token_doc.get("used_at"):
            log.warning(
                "otp_verification_failed",
                user_id=user_id,
                reason="already_used",
                token_type=token_type,
            )
            return False, "Verification code has already been used"

        # Check max attempts (stored in token doc)
        if token_doc.get("attempts", 0) >= MAX_VERIFICATION_ATTEMPTS:
            log.warning(
                "otp_verification_failed",
                user_id=user_id,
                reason="max_attempts",
                token_type=token_type,
            )
            return False, "Too many failed attempts. Please request a new code."

        # Mark token as used
        if not mark_token_as_used(token_doc["_id"]):
            log.error(
                "otp_mark_used_failed",
                user_id=user_id,
                token_id=str(token_doc["_id"]),
            )
            return False, "Failed to verify code"

        log.info(
            "otp_verified_success",
            user_id=user_id,
            token_id=str(token_doc["_id"]),
            token_type=token_type,
        )

        return True, None

    except Exception as e:
        log.error(
            "otp_verification_error",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return False, "An error occurred during verification"


def is_rate_limited(user_id: str, token_type: str) -> bool:
    """
    Check if a user is rate limited for a specific token type

    Args:
        user_id: User's MongoDB ObjectId as string
        token_type: Type of token to check

    Returns:
        True if rate limited, False otherwise
    """
    try:
        recent_count = count_recent_tokens(user_id, token_type, 60)
        return recent_count >= MAX_TOKENS_PER_HOUR
    except Exception:
        return False
