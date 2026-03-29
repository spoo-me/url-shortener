"""
Global exception handlers with content negotiation.

API requests (JSON Accept, /api/, /auth/, /oauth/ prefixes) get JSON errors.
Browser/page requests get the error.html template.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError as PydanticValidationError
from slowapi.errors import RateLimitExceeded

from errors import AppError
from shared.logging import get_logger

log = get_logger(__name__)

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)


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
            status_code=400,
            content={"error": "Validation error", "code": "validation_error"},
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_error_handler(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": "Validation error", "code": "validation_error"},
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
