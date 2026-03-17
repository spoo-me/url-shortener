"""
Security middleware — CORS configuration and request body size limit.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from config import AppSettings


def configure_cors(app: FastAPI, settings: AppSettings) -> None:
    """Add CORS middleware from settings. Defaults to allow-all with credentials."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class MaxContentLengthMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds the configured limit."""

    def __init__(self, app, max_content_length: int = 1_048_576) -> None:
        super().__init__(app)
        self.max_content_length = max_content_length

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        content_length = request.headers.get("content-length")
        try:
            parsed = int(content_length) if content_length else None
        except ValueError:
            parsed = None
        if parsed is not None and parsed > self.max_content_length:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Request body too large",
                    "code": "payload_too_large",
                },
            )
        return await call_next(request)
