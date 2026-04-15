"""
CredentialService — login, registration, and token refresh.

Handles email+password authentication flows.  JWT issuance is delegated
to TokenFactory.  OTP creation for post-registration verification emails
is delegated to OtpService.
"""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from errors import AuthenticationError, ConflictError, ValidationError
from infrastructure.email.protocol import EmailProvider
from repositories.user_repository import UserRepository
from schemas.models.token import TOKEN_TYPE_EMAIL_VERIFY
from schemas.models.user import UserDoc, UserPlan, UserStatus
from schemas.results import AuthResult
from services.auth.otp import OtpService
from services.token_factory import TokenFactory
from shared.crypto import hash_password, verify_password
from shared.logging import get_logger
from shared.validators import validate_account_password

log = get_logger(__name__)


class CredentialService:
    """Login, registration, and token refresh.

    Args:
        user_repo:    Repository for the ``users`` collection.
        otp_service:  Shared OTP helper (for post-registration verification).
        email:        Email provider (ZeptoMail in production, mock in tests).
        token_factory: JWT token generation and verification.
        account_password_min_length: Minimum password length.
        account_password_max_length: Maximum password length.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        otp_service: OtpService,
        email: EmailProvider,
        token_factory: TokenFactory,
        account_password_min_length: int = 8,
        account_password_max_length: int = 128,
    ) -> None:
        self._user_repo = user_repo
        self._otp = otp_service
        self._email = email
        self._tokens = token_factory
        self._password_min_length = account_password_min_length
        self._password_max_length = account_password_max_length

    async def login(self, email: str, password: str) -> AuthResult:
        """Authenticate with email + password.

        Raises:
            AuthenticationError: Invalid credentials (does not distinguish
                between unknown email and wrong password — prevents enumeration).
        """
        svc_log = log.bind(op="auth.login")

        user = await self._user_repo.find_by_email(email)
        if not user or not user.password_hash:
            svc_log.info(
                "login_failed",
                reason="invalid_credentials",
                email_exists=bool(user),
            )
            raise AuthenticationError("invalid credentials")

        if not verify_password(password, user.password_hash):
            svc_log.info(
                "login_failed", reason="invalid_password", user_id=str(user.id)
            )
            raise AuthenticationError("invalid credentials")

        svc_log.info("login_success", user_id=str(user.id), auth_method="password")
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
        svc_log = log.bind(op="auth.register")

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
            svc_log.info("registration_failed", reason="email_exists")
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
            svc_log.info("registration_failed", reason="race_condition_duplicate")
            raise ConflictError("email already registered") from None

        user_doc.id = user_id

        svc_log.info(
            "user_registered",
            user_id=str(user_id),
            auth_method="password",
            has_username=bool(user_name),
        )

        access_token, refresh_token = self._tokens.issue_tokens(user_doc, "pwd")

        # Send verification email — non-fatal, do not fail registration on error
        verification_sent = False
        try:
            otp_code = await self._otp.create_otp(
                user_id, email, TOKEN_TYPE_EMAIL_VERIFY
            )
            await self._email.send_verification_email(email, user_name, otp_code)
            verification_sent = True
            svc_log.info("registration_verification_email_sent", user_id=str(user_id))
        except Exception as exc:
            svc_log.error(
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
        svc_log = log.bind(op="auth.refresh")

        try:
            claims = self._tokens.verify_token(refresh_token_str, token_type="refresh")
        except AuthenticationError:
            raise

        user_id = claims.get("sub")
        user = await self._user_repo.find_by_id(ObjectId(user_id))
        if not user or user.status != UserStatus.ACTIVE:
            svc_log.info(
                "token_refresh_failed",
                reason="user_not_found_or_inactive",
                user_id=user_id,
            )
            raise AuthenticationError("invalid or expired refresh token")

        amr = claims.get("amr", ["pwd"])[0]
        app_id = claims.get("app_id")

        svc_log.info("token_refreshed", user_id=user_id, amr=amr, app_id=app_id)
        new_access, new_refresh = self._tokens.issue_tokens(user, amr, app_id=app_id)
        return AuthResult(
            user=user,
            access_token=new_access,
            refresh_token=new_refresh,
            app_id=app_id,
        )
