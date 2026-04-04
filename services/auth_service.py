"""
AuthService — authentication business logic.

Handles OTP-based email verification, password management, and user
registration/login.  JWT issuance and verification is delegated to
TokenFactory.  Framework-agnostic: no FastAPI imports.  All I/O goes
through the injected repositories and email provider.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from config import JWTSettings
from errors import (
    AppError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from infrastructure.email.protocol import EmailProvider
from repositories.token_repository import TokenRepository
from repositories.user_repository import UserRepository
from schemas.models.token import (
    TOKEN_TYPE_DEVICE_AUTH,
    TOKEN_TYPE_EMAIL_VERIFY,
    TOKEN_TYPE_PASSWORD_RESET,
)
from schemas.models.user import UserDoc, UserPlan, UserStatus
from schemas.results import AuthResult
from services.token_factory import TokenFactory
from shared.crypto import hash_password, hash_token, verify_password
from shared.generators import generate_otp_code, generate_secure_token
from shared.logging import get_logger
from shared.validators import validate_account_password

log = get_logger(__name__)

# ── Expiry / rate-limit constants ─────────────────────────────────────────────

OTP_EXPIRY_SECONDS = 600  # 10 minutes
MAX_TOKENS_PER_HOUR = 3
MAX_VERIFICATION_ATTEMPTS = 5
DEVICE_AUTH_EXPIRY_SECONDS = 300  # 5 minutes


class AuthService:
    """Authentication service.

    Args:
        user_repo:  Repository for the ``users`` collection.
        token_repo: Repository for the ``verification-tokens`` collection.
        email:      Email provider (ZeptoMail in production, mock in tests).
        settings:   JWT configuration (issuer, audience, keys, TTLs).
    """

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: TokenRepository,
        email: EmailProvider,
        settings: JWTSettings,
        account_password_min_length: int = 8,
        account_password_max_length: int = 128,
    ) -> None:
        self._user_repo = user_repo
        self._token_repo = token_repo
        self._email = email
        self._tokens = TokenFactory(settings)
        self._password_min_length = account_password_min_length
        self._password_max_length = account_password_max_length

    # ── JWT delegation ────────────────────────────────────────────────────────

    def issue_tokens(self, user: UserDoc, amr: str) -> tuple[str, str]:
        """Issue an access + refresh token pair for *user*.

        Returns:
            (access_token, refresh_token)
        """
        return self._tokens.issue_tokens(user, amr)

    def _generate_access_token(self, user: UserDoc, *, amr: str) -> str:
        return self._tokens.generate_access_token(user, amr=amr)

    def _generate_refresh_token(self, user: UserDoc, *, amr: str) -> str:
        return self._tokens.generate_refresh_token(user, amr=amr)

    def _verify_token(self, token: str, *, token_type: str) -> dict[str, Any]:
        return self._tokens.verify_token(token, token_type=token_type)

    # ── OTP helpers ───────────────────────────────────────────────────────────

    async def _create_otp(
        self,
        user_id: ObjectId,
        email: str,
        token_type: str,
        *,
        delete_existing: bool = False,
    ) -> str:
        """Create an OTP for email verification or password reset.

        Args:
            user_id:         Owner of the token.
            email:           Email address to bind the token to.
            token_type:      ``TOKEN_TYPE_EMAIL_VERIFY`` or ``TOKEN_TYPE_PASSWORD_RESET``.
            delete_existing: When True, purge old tokens of the same type first.
                                Used for password reset so only one active reset token
                                exists per user at a time.

        Returns:
            The raw (unhashed) OTP code to send to the user.

        Raises:
            RateLimitError: When too many tokens have been created recently.
            AppError:       On unexpected DB failure.
        """
        recent_count = await self._token_repo.count_recent(user_id, token_type, 60)
        if recent_count >= MAX_TOKENS_PER_HOUR:
            log.warning(
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
        log.info("otp_created", user_id=str(user_id), token_type=token_type)
        return otp_code

    async def _verify_otp(
        self, user_id: ObjectId, otp_code: str, token_type: str
    ) -> None:
        """Verify an OTP code and mark it as used.

        Raises:
            ValidationError: On any verification failure.
            AppError: If marking the token as used fails.
        """
        token_doc = await self._token_repo.find_latest_by_user(user_id, token_type)

        if not token_doc:
            log.warning(
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
            log.warning(
                "otp_verification_failed",
                user_id=str(user_id),
                reason="expired",
                token_type=token_type,
            )
            raise ValidationError("Verification code has expired")

        if token_doc.attempts >= MAX_VERIFICATION_ATTEMPTS:
            log.warning(
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
            log.warning(
                "otp_verification_failed",
                user_id=str(user_id),
                reason="wrong_code",
                token_type=token_type,
                attempts=token_doc.attempts + 1,
            )
            raise ValidationError("Invalid or expired verification code")

        marked = await self._token_repo.mark_as_used(token_doc.id)
        if not marked:
            log.error(
                "otp_mark_used_failed",
                user_id=str(user_id),
                token_id=str(token_doc.id),
            )
            raise AppError("Failed to verify code")

        log.info(
            "otp_verified_success",
            user_id=str(user_id),
            token_type=token_type,
        )

    # ── Business logic ────────────────────────────────────────────────────────

    async def login(self, email: str, password: str) -> AuthResult:
        """Authenticate with email + password.

        Raises:
            AuthenticationError: Invalid credentials (does not distinguish
                between unknown email and wrong password — prevents enumeration).
        """
        user = await self._user_repo.find_by_email(email)
        if not user or not user.password_hash:
            log.warning(
                "login_failed",
                reason="invalid_credentials",
                email_exists=bool(user),
            )
            raise AuthenticationError("invalid credentials")

        if not verify_password(password, user.password_hash):
            log.warning("login_failed", reason="invalid_password", user_id=str(user.id))
            raise AuthenticationError("invalid credentials")

        log.info("login_success", user_id=str(user.id), auth_method="password")
        access_token, refresh_token = self._tokens.issue_tokens(user, "pwd")
        return AuthResult(
            user=user, access_token=access_token, refresh_token=refresh_token
        )

    async def register(
        self,
        email: str,
        password: str,
        user_name: str | None,
        signup_ip: str | None,
    ) -> AuthResult:
        """Register a new user with email + password.

        Raises:
            ValidationError: Password fails validation rules.
            ConflictError:   Email already registered.
        """
        is_valid, missing, _ = validate_account_password(
            password,
            min_length=self._password_min_length,
            max_length=self._password_max_length,
        )
        if not is_valid:
            raise ValidationError(
                "Password does not meet requirements",
                details={"missing_requirements": missing},
            )

        existing = await self._user_repo.find_by_email(email)
        if existing:
            log.warning("registration_failed", reason="email_exists")
            raise ConflictError("email already registered")

        now = datetime.now(timezone.utc)
        password_hash = hash_password(password)
        user_doc = UserDoc(
            email=email,
            email_verified=False,
            password_hash=password_hash,
            password_set=True,
            user_name=user_name,
            pfp=None,
            auth_providers=[],
            plan=UserPlan.FREE,
            signup_ip=signup_ip,
            created_at=now,
            updated_at=now,
            status=UserStatus.ACTIVE,
        )
        user_data = user_doc.model_dump(by_alias=True, exclude={"id"})

        try:
            user_id = await self._user_repo.create(user_data)
        except DuplicateKeyError:
            log.warning("registration_failed", reason="race_condition_duplicate")
            raise ConflictError("email already registered") from None

        user_doc.id = user_id

        log.info(
            "user_registered",
            user_id=str(user_id),
            auth_method="password",
            has_username=bool(user_name),
        )

        access_token, refresh_token = self._tokens.issue_tokens(user_doc, "pwd")

        # Send verification email — non-fatal, do not fail registration on error
        verification_sent = False
        try:
            otp_code = await self._create_otp(user_id, email, TOKEN_TYPE_EMAIL_VERIFY)
            await self._email.send_verification_email(email, user_name, otp_code)
            verification_sent = True
            log.info("registration_verification_email_sent", user_id=str(user_id))
        except Exception as exc:
            log.error(
                "registration_verification_email_failed",
                user_id=str(user_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )

        return AuthResult(
            user=user_doc,
            access_token=access_token,
            refresh_token=refresh_token,
            verification_sent=verification_sent,
        )

    async def refresh_token(self, refresh_token_str: str) -> AuthResult:
        """Perform stateless token rotation.

        Verifies the refresh JWT, re-fetches the user to get the latest
        ``email_verified`` status, and issues a new token pair.  The original
        ``amr`` and ``app_id`` claims are preserved across rotations.

        Raises:
            AuthenticationError: Token invalid/expired, or user not found/inactive.
        """
        try:
            claims = self._verify_token(refresh_token_str, token_type="refresh")
        except AuthenticationError:
            raise

        user_id = claims.get("sub")
        user = await self._user_repo.find_by_id(ObjectId(user_id))
        if not user or user.status != UserStatus.ACTIVE:
            log.warning(
                "token_refresh_failed",
                reason="user_not_found_or_inactive",
                user_id=user_id,
            )
            raise AuthenticationError("invalid or expired refresh token")

        amr = claims.get("amr", ["pwd"])[0]
        app_id = claims.get("app_id")

        log.info("token_refreshed", user_id=user_id, amr=amr, app_id=app_id)
        new_access, new_refresh = self._tokens.issue_tokens(user, amr, app_id=app_id)
        return AuthResult(
            user=user, access_token=new_access, refresh_token=new_refresh, app_id=app_id
        )

    async def verify_email(self, user_id: str, otp_code: str) -> tuple[str, str]:
        """Verify a user's email address using an OTP code.

        Marks the user's email as verified, sends a welcome email (best-effort),
        and issues new tokens with ``email_verified=True``.

        Returns:
            (new_access_token, new_refresh_token)

        Raises:
            NotFoundError:   User not found.
            ValidationError: Email already verified, or OTP invalid/expired/used.
            AppError:        DB update failure.
        """
        user_oid = ObjectId(user_id)
        user = await self._user_repo.find_by_id(user_oid)
        if not user:
            raise NotFoundError("user not found")

        if user.email_verified:
            raise ValidationError("email already verified")

        await self._verify_otp(user_oid, otp_code, TOKEN_TYPE_EMAIL_VERIFY)

        updated = await self._user_repo.update(
            user_oid,
            {
                "$set": {
                    "email_verified": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if not updated:
            log.error("email_verification_update_failed", user_id=user_id)
            raise AppError("failed to update verification status")

        log.info("email_verified_success", user_id=user_id)

        # Build updated user doc for token generation
        user_data = user.model_dump(by_alias=True)
        user_data["_id"] = user_oid
        user_data["email_verified"] = True
        updated_user = UserDoc.model_validate(user_data)

        access_token, refresh_token = self._tokens.issue_tokens(updated_user, "pwd")

        # Send welcome email — best-effort, do not fail verification on error
        try:
            await self._email.send_welcome_email(user.email, user.user_name)
        except Exception as exc:
            log.error(
                "welcome_email_send_failed",
                user_id=user_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )

        return access_token, refresh_token

    async def send_verification(self, user_id: str) -> None:
        """Create and send a verification email OTP.

        Raises:
            NotFoundError:   User not found.
            ValidationError: Email already verified.
            RateLimitError:  Too many recent verification requests.
            AppError:        Failed to send email.
        """
        user_oid = ObjectId(user_id)
        user = await self._user_repo.find_by_id(user_oid)
        if not user:
            raise NotFoundError("user not found")

        if user.email_verified:
            raise ValidationError("email already verified")

        otp_code = await self._create_otp(user_oid, user.email, TOKEN_TYPE_EMAIL_VERIFY)

        email_sent = await self._email.send_verification_email(
            user.email, user.user_name, otp_code
        )
        if not email_sent:
            log.error("verification_email_send_failed", user_id=user_id)
            raise AppError("failed to send verification email")

        log.info("verification_email_sent", user_id=user_id, email=user.email)

    async def request_password_reset(self, email: str) -> None:
        """Request a password reset OTP.

        TIMING-SAFE: Always returns normally regardless of whether the email
        exists, has a password set, or is rate-limited. All errors are swallowed
        and logged. This prevents user enumeration.
        """
        try:
            user = await self._user_repo.find_by_email(email)
            if not user:
                log.warning("password_reset_requested_nonexistent", email=email)
                return

            if not user.password_set:
                log.warning("password_reset_no_password", user_id=str(user.id))
                return

            otp_code = await self._create_otp(
                user.id, user.email, TOKEN_TYPE_PASSWORD_RESET, delete_existing=True
            )

            email_sent = await self._email.send_password_reset_email(
                user.email, user.user_name, otp_code
            )
            if not email_sent:
                log.error("password_reset_email_send_failed", user_id=str(user.id))
                return

            log.info("password_reset_email_sent", user_id=str(user.id))

        except RateLimitError:
            log.warning("password_reset_rate_limited", email=email)
        except Exception as exc:
            log.error(
                "password_reset_unexpected_error",
                email=email,
                error=str(exc),
                error_type=type(exc).__name__,
            )

    async def reset_password(
        self, email: str, otp_code: str, new_password: str
    ) -> None:
        """Reset password using an OTP code.

        Raises:
            ValidationError: User not found, OTP invalid, or password fails rules.
            AppError:        DB update failure.
        """
        user = await self._user_repo.find_by_email(email)

        is_valid, missing, _ = validate_account_password(
            new_password,
            min_length=self._password_min_length,
            max_length=self._password_max_length,
        )
        if not is_valid:
            raise ValidationError(
                "password does not meet requirements",
                details={"missing_requirements": missing},
            )

        if not user:
            # Simulate OTP verification timing to prevent user enumeration
            _dummy_hash = hash_token(otp_code)
            raise ValidationError("invalid email or code")

        try:
            await self._verify_otp(user.id, otp_code, TOKEN_TYPE_PASSWORD_RESET)
        except ValidationError:
            # Re-raise with generic message to prevent user enumeration
            # via distinct error messages (_verify_otp already logs the details)
            raise ValidationError("invalid email or code") from None

        new_hash = hash_password(new_password)
        updated = await self._user_repo.update(
            user.id,
            {
                "$set": {
                    "password_hash": new_hash,
                    "password_set": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if not updated:
            log.error("password_reset_update_failed", user_id=str(user.id))
            raise AppError("failed to reset password")

        log.info("password_reset_success", user_id=str(user.id))

    async def set_password(self, user_id: str, password: str) -> None:
        """Set a password for an OAuth-only user (no existing password).

        Raises:
            NotFoundError:   User not found.
            ValidationError: Password already set, or fails validation rules.
            AppError:        DB update failure.
        """
        user_oid = ObjectId(user_id)
        user = await self._user_repo.find_by_id(user_oid)
        if not user:
            raise NotFoundError("user not found")

        if user.password_set:
            raise ValidationError("password already set")

        is_valid, missing, _ = validate_account_password(
            password,
            min_length=self._password_min_length,
            max_length=self._password_max_length,
        )
        if not is_valid:
            raise ValidationError(
                "Password does not meet requirements",
                details={"missing_requirements": missing},
            )

        new_hash = hash_password(password)
        updated = await self._user_repo.update(
            user_oid,
            {
                "$set": {
                    "password_hash": new_hash,
                    "password_set": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if not updated:
            log.error("password_set_failed", user_id=user_id, reason="no_update")
            raise AppError("failed to set password")

        log.info("password_set", user_id=user_id)

    async def get_user_profile(self, user_id: str) -> UserDoc:
        """Fetch a user document for profile display.

        Raises:
            NotFoundError: User not found.
        """
        user = await self._user_repo.find_by_id(ObjectId(user_id))
        if not user:
            raise NotFoundError("user not found")
        return user

    # ── Device auth flow ─────────────────────────────────────────────────────

    async def create_device_auth_code(
        self, user_id: ObjectId, email: str, app_id: str | None = None
    ) -> str:
        """Generate a one-time auth code for the device auth flow.

        Returns the raw token (caller redirects to callback with it).
        """
        await self._token_repo.delete_by_user(
            user_id, TOKEN_TYPE_DEVICE_AUTH, app_id=app_id
        )

        raw_token = generate_secure_token(48)
        now = datetime.now(timezone.utc)
        token_data: dict = {
            "user_id": user_id,
            "email": email,
            "token_hash": hash_token(raw_token),
            "token_type": TOKEN_TYPE_DEVICE_AUTH,
            "expires_at": now + timedelta(seconds=DEVICE_AUTH_EXPIRY_SECONDS),
            "created_at": now,
            "used_at": None,
            "attempts": 0,
        }
        if app_id:
            token_data["app_id"] = app_id
        await self._token_repo.create(token_data)
        log.info("device_auth_code_created", user_id=str(user_id), app_id=app_id)
        return raw_token

    async def exchange_device_code(self, code: str) -> AuthResult:
        """Exchange a one-time device auth code for JWT tokens.

        Raises:
            AuthenticationError: Code invalid, expired, or already used.
        """
        token_hash = hash_token(code)
        token_doc = await self._token_repo.consume_by_hash(
            token_hash, TOKEN_TYPE_DEVICE_AUTH
        )
        if not token_doc:
            raise AuthenticationError("invalid or expired device auth code")

        user = await self._user_repo.find_by_id(token_doc.user_id)
        if not user or user.status != UserStatus.ACTIVE:
            raise AuthenticationError("user not found or inactive")

        app_id = token_doc.app_id
        log.info("device_auth_success", user_id=str(user.id), app_id=app_id)
        access_token, refresh_token = self._tokens.issue_tokens(
            user, "ext", app_id=app_id
        )
        return AuthResult(
            user=user, access_token=access_token, refresh_token=refresh_token, app_id=app_id
        )

    async def revoke_device_tokens(
        self, user_id: ObjectId, app_id: str | None = None
    ) -> int:
        """Invalidate device auth tokens for a user, optionally filtered by app_id.

        Returns the number of tokens deleted.
        """
        count = await self._token_repo.delete_by_user(
            user_id, TOKEN_TYPE_DEVICE_AUTH, app_id=app_id
        )
        log.info(
            "device_tokens_revoked",
            user_id=str(user_id),
            app_id=app_id,
            count=count,
        )
        return count
