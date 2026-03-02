"""
AuthService — authentication business logic.

Handles JWT issuance/verification, OTP-based email verification, password
management, and OAuth account linking.  Framework-agnostic: no FastAPI
imports.  All I/O goes through the injected repository and email provider.

Phase 8 (skeleton): only JWT helpers are implemented.  Later phases add
login(), register(), refresh_token(), verify_email(), etc.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import jwt as pyjwt

from config import JWTSettings
from errors import AuthenticationError
from infrastructure.email.protocol import EmailProvider
from repositories.token_repository import TokenRepository
from repositories.user_repository import UserRepository
from schemas.models.user import UserDoc
from shared.crypto import hash_password, hash_token, verify_password
from shared.generators import generate_otp_code

# ── Token-type constants ──────────────────────────────────────────────────────

TOKEN_TYPE_EMAIL_VERIFY = "email_verify"
TOKEN_TYPE_PASSWORD_RESET = "password_reset"

# ── Expiry / rate-limit constants ─────────────────────────────────────────────

OTP_EXPIRY_SECONDS = 600          # 10 minutes
TOKEN_EXPIRY_SECONDS = 900        # 15 minutes
MAX_TOKENS_PER_HOUR = 3
MAX_VERIFICATION_ATTEMPTS = 5


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
    ) -> None:
        self._user_repo = user_repo
        self._token_repo = token_repo
        self._email = email
        self._settings = settings

    # ── JWT helpers ───────────────────────────────────────────────────────────

    def _jwt_algorithm(self) -> str:
        """Return 'RS256' when RSA keys are configured, 'HS256' otherwise."""
        return "RS256" if self._settings.use_rs256 else "HS256"

    def _jwt_signing_key(self) -> str:
        """Return the key used to sign tokens."""
        if self._settings.use_rs256:
            return self._settings.jwt_private_key
        return self._settings.jwt_secret

    def _jwt_verification_key(self) -> str:
        """Return the key used to verify tokens."""
        if self._settings.use_rs256:
            return self._settings.jwt_public_key
        return self._settings.jwt_secret

    def _generate_access_token(self, user: UserDoc, *, amr: str) -> str:
        """Issue a signed JWT access token for *user*.

        Claims:
            iss            — issuer (from settings)
            aud            — audience (from settings)
            sub            — user ObjectId as string
            iat            — issued-at (UTC epoch seconds)
            exp            — expiry (iat + access_token_ttl_seconds)
            amr            — authentication method reference list, e.g. ["pwd"]
            email_verified — bool from the user document

        Returns:
            Signed JWT string.
        """
        now = int(datetime.now(timezone.utc).timestamp())
        payload: dict[str, Any] = {
            "iss": self._settings.jwt_issuer,
            "aud": self._settings.jwt_audience,
            "sub": str(user.id),
            "iat": now,
            "exp": now + self._settings.access_token_ttl_seconds,
            "amr": [amr],
            "email_verified": user.email_verified,
        }
        return pyjwt.encode(
            payload,
            self._jwt_signing_key(),
            algorithm=self._jwt_algorithm(),
        )

    def _generate_refresh_token(self, user: UserDoc, *, amr: str) -> str:
        """Issue a signed JWT refresh token for *user*.

        Identical to the access token but includes ``"type": "refresh"`` and
        uses ``refresh_token_ttl_seconds`` for the expiry window.

        Returns:
            Signed JWT string.
        """
        now = int(datetime.now(timezone.utc).timestamp())
        payload: dict[str, Any] = {
            "iss": self._settings.jwt_issuer,
            "aud": self._settings.jwt_audience,
            "sub": str(user.id),
            "iat": now,
            "exp": now + self._settings.refresh_token_ttl_seconds,
            "amr": [amr],
            "email_verified": user.email_verified,
            "type": "refresh",
        }
        return pyjwt.encode(
            payload,
            self._jwt_signing_key(),
            algorithm=self._jwt_algorithm(),
        )

    def _verify_token(self, token: str, *, token_type: str) -> dict[str, Any]:
        """Decode and validate *token*.

        Args:
            token:      Raw JWT string.
            token_type: ``"access"`` or ``"refresh"``.  When ``"refresh"``,
                        the payload must contain ``"type": "refresh"``; any
                        token lacking that field is rejected with
                        :class:`~errors.AuthenticationError`.

        Returns:
            The decoded payload dict.

        Raises:
            AuthenticationError: On any decode / validation failure, or when
                a refresh token is expected but the payload has no ``type``
                field.
        """
        try:
            payload: dict[str, Any] = pyjwt.decode(
                token,
                self._jwt_verification_key(),
                algorithms=[self._jwt_algorithm()],
                audience=self._settings.jwt_audience,
                issuer=self._settings.jwt_issuer,
            )
        except pyjwt.PyJWTError as exc:
            raise AuthenticationError(f"Invalid token: {exc}") from exc

        if token_type == "refresh" and payload.get("type") != "refresh":
            raise AuthenticationError(
                "Token is not a refresh token — 'type' field missing or incorrect."
            )

        return payload
