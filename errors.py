"""
Application error hierarchy.

AppError is the base for all typed errors.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error. All typed errors inherit from this."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.field = field
        self.details = details

    def to_dict(self) -> dict:
        payload: dict = {"error": self.message, "code": self.error_code}
        if self.field is not None:
            payload["field"] = self.field
        if self.details is not None:
            payload["details"] = self.details
        return payload


class ValidationError(AppError):
    status_code = 400
    error_code = "validation_error"


class AuthenticationError(AppError):
    status_code = 401
    error_code = "authentication_error"


class ForbiddenError(AppError):
    status_code = 403
    error_code = "forbidden"


class EmailNotVerifiedError(ForbiddenError):
    """Raised when email verification is required before proceeding."""

    error_code = "EMAIL_NOT_VERIFIED"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["message"] = (
            "You must verify your email address before creating resources. "
            "Check your inbox for the verification code."
        )
        return d


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class ConflictError(AppError):
    status_code = 409
    error_code = "conflict"


class GoneError(AppError):
    status_code = 410
    error_code = "gone"


class RateLimitError(AppError):
    status_code = 429
    error_code = "rate_limit_exceeded"
