"""
Global exception handlers with content negotiation.

API requests (JSON Accept, /api/, /auth/, /oauth/ prefixes) get JSON errors.
Browser/page requests get the error.html template.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError as PydanticValidationError
from slowapi.errors import RateLimitExceeded

from errors import AppError
from infrastructure.logging import get_logger
from infrastructure.templates import templates

log = get_logger(__name__)


def _field_loc(err: dict) -> str:
    """Extract a readable field name from a Pydantic error's loc tuple."""
    loc = err.get("loc", ())
    parts = [
        str(p) for p in loc if p not in ("body", "query", "path", "header", "cookie")
    ]
    return ".".join(parts) if parts else "input"


def _validation_error_response(errors: list[dict]) -> dict:
    """Build a JSON-serialisable error dict from Pydantic validation errors.

    Follows the same ``{error, code, field?, details?}`` shape used by
    ``AppError.to_dict`` so every error response is structurally identical.
    """
    details = [
        {"field": _field_loc(e), "error": e.get("msg", "invalid value")} for e in errors
    ]

    if len(details) == 1:
        return {
            "error": f"{details[0]['field']}: {details[0]['error']}",
            "code": "validation_error",
            "field": details[0]["field"],
        }

    fields = list(dict.fromkeys(d["field"] for d in details))
    return {
        "error": f"Validation failed for: {', '.join(fields)}",
        "code": "validation_error",
        "details": details,
    }


def _wants_json(request: Request) -> bool:
    """Determine if the request expects a JSON response."""
    accept = request.headers.get("accept", "")
    content_type = request.headers.get("content-type", "")
    path = request.url.path
    return (
        "application/json" in accept
        or content_type.startswith("application/json")
        or path.startswith("/api/")
        or path.startswith("/auth/")
        or path.startswith("/oauth/")
    )


def _error_html(request: Request, status_code: int, message: str) -> Response:
    """Render error.html template for browser requests."""
    host_url = str(request.base_url)
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "error_code": str(status_code),
            "error_message": message,
            "host_url": host_url,
        },
        status_code=status_code,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers with content negotiation."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> Response:
        if _wants_json(request):
            return JSONResponse(status_code=exc.status_code, content=exc.to_dict())
        return _error_html(request, exc.status_code, exc.message.upper())

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Validation errors only occur on typed API/auth routes — always JSON
        return JSONResponse(
            status_code=422,
            content=_validation_error_response(exc.errors()),
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_error_handler(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_validation_error_response(exc.errors()),
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
        if _wants_json(request):
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests", "code": "rate_limit_exceeded"},
            )
        return _error_html(request, 429, "TOO MANY REQUESTS")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
        log.error(
            "unhandled_exception",
            error=str(exc),
            error_type=type(exc).__name__,
            path=request.url.path,
        )
        if _wants_json(request):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "An internal server error occurred.",
                    "code": "internal_error",
                },
            )
        return _error_html(request, 500, "INTERNAL SERVER ERROR")
