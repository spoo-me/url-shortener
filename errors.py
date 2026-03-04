"""
Application error hierarchy and FastAPI exception handlers.

AppError is the base for all typed errors. The global exception handler
converts AppError subclasses to consistent JSON responses.

Non-AppError exceptions bubble up as 500s (with Sentry reporting in production).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError


class AppError(Exception):
    """Base application error. All typed errors inherit from this."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        field: Optional[str] = None,
        details: Optional[Any] = None,
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


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "Validation error", "code": "validation_error"},
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_error_handler(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        # pydantic.ValidationError from Depends() resolution is not automatically
        # wrapped as RequestValidationError — handle it here to return 422.
        return JSONResponse(
            status_code=422,
            content={"error": "Validation error", "code": "validation_error"},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Sentry integration: if sentry_sdk is initialized it will auto-capture
        # unhandled exceptions before this handler fires.
        return JSONResponse(
            status_code=500,
            content={
                "error": "An internal server error occurred.",
                "code": "internal_error",
            },
        )
