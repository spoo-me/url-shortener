"""
OtpService — OTP creation and verification.

Shared by EmailVerificationService and PasswordService.  Stateless apart
from the injected TokenRepository.  All rate-limiting and expiry logic
lives here so callers don't duplicate it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bson import ObjectId

from errors import AppError, RateLimitError, ValidationError
from repositories.token_repository import TokenRepository
from schemas.models.token import TOKEN_TYPE_PASSWORD_RESET
from shared.crypto import hash_token
from shared.generators import generate_otp_code
from shared.logging import get_logger

log = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

OTP_EXPIRY_SECONDS = 600  # 10 minutes
MAX_TOKENS_PER_HOUR = 3
MAX_VERIFICATION_ATTEMPTS = 5


class OtpService:
    """OTP creation and verification against the token repository.

    Args:
        token_repo: Repository for the ``verification-tokens`` collection.
    """

    def __init__(self, token_repo: TokenRepository) -> None:
        self._token_repo = token_repo

    async def create_otp(
        self,
        user_id: ObjectId,
        email: str,
        token_type: str,
        *,
        delete_existing: bool = False,
    ) -> str:
        """Create an OTP for email verification or password reset.

        Returns:
            The raw (unhashed) OTP code to send to the user.

        Raises:
            RateLimitError: When too many tokens have been created recently.
            AppError:       On unexpected DB failure.
        """
        svc_log = log.bind(op="otp.create")

        recent_count = await self._token_repo.count_recent(user_id, token_type, 60)
        if recent_count >= MAX_TOKENS_PER_HOUR:
            svc_log.info(
                "otp_rate_limited",
                user_id=str(user_id),
                token_type=token_type,
                count=recent_count,
            )
            msg = (
                "Too many password reset attempts. Please try again later."
                if token_type == TOKEN_TYPE_PASSWORD_RESET
                else "Too many verification attempts. Please try again later."
            )
            raise RateLimitError(msg)

        if delete_existing:
            await self._token_repo.delete_by_user(user_id, token_type)

        otp_code = generate_otp_code()
        now = datetime.now(timezone.utc)
        await self._token_repo.create(
            {
                "user_id": user_id,
                "email": email,
                "token_hash": hash_token(otp_code),
                "token_type": token_type,
                "expires_at": now + timedelta(seconds=OTP_EXPIRY_SECONDS),
                "created_at": now,
                "used_at": None,
                "attempts": 0,
            }
        )
        svc_log.info("otp_created", user_id=str(user_id), token_type=token_type)
        return otp_code

    async def verify_otp(
        self, user_id: ObjectId, otp_code: str, token_type: str
    ) -> None:
        """Verify an OTP code and mark it as used.

        Raises:
            ValidationError: On any verification failure.
            AppError: If marking the token as used fails.
        """
        svc_log = log.bind(op="otp.verify")

        token_doc = await self._token_repo.find_latest_by_user(user_id, token_type)

        if not token_doc:
            svc_log.info(
                "otp_verification_failed",
                user_id=str(user_id),
                reason="token_not_found",
                token_type=token_type,
            )
            raise ValidationError("Invalid or expired verification code")

        expires_at = token_doc.expires_at
        if not expires_at.tzinfo:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= datetime.now(timezone.utc):
            svc_log.info(
                "otp_verification_failed",
                user_id=str(user_id),
                reason="expired",
                token_type=token_type,
            )
            raise ValidationError("Verification code has expired")

        if token_doc.attempts >= MAX_VERIFICATION_ATTEMPTS:
            svc_log.info(
                "otp_verification_failed",
                user_id=str(user_id),
                reason="max_attempts",
                token_type=token_type,
            )
            raise ValidationError(
                "Too many failed attempts. Please request a new code."
            )

        # Compare hash — increment attempts on mismatch
        otp_hash = hash_token(otp_code)
        if token_doc.token_hash != otp_hash:
            await self._token_repo.increment_attempts(token_doc.id)
            svc_log.info(
                "otp_verification_failed",
                user_id=str(user_id),
                reason="wrong_code",
                token_type=token_type,
                attempts=token_doc.attempts + 1,
            )
            raise ValidationError("Invalid or expired verification code")

        marked = await self._token_repo.mark_as_used(token_doc.id)
        if not marked:
            svc_log.error(
                "otp_mark_used_failed",
                user_id=str(user_id),
                token_id=str(token_doc.id),
            )
            raise AppError("Failed to verify code")

        svc_log.info(
            "otp_verified_success",
            user_id=str(user_id),
            token_type=token_type,
        )
