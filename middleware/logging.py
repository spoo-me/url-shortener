"""
Request logging middleware — generates request_id, logs request/response metadata.

Uses structlog contextvars for propagation so service/repo layers can access
request_id without explicit parameter passing.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from shared.ip_utils import get_client_ip
from shared.logging import get_logger, hash_ip

log = get_logger("spoo.request")

# Paths to skip detailed logging (high-volume, low-value)
_SKIP_PATHS = frozenset({"/health", "/favicon.ico"})


def _generate_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = _generate_request_id()
        start = time.perf_counter()
        path = request.url.path

        # Bind request context to structlog contextvars — available in all
        # downstream log calls (services, repositories, etc.)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            http_method=request.method,
            http_path=path,
        )

        response = await call_next(request)

        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id

        if path not in _SKIP_PATHS:
            status = response.status_code
            log_fn = (
                log.error
                if status >= 500
                else (log.warning if status >= 400 else log.info)
            )
            log_fn(
                "request_completed",
                method=request.method,
                path=path,
                status_code=status,
                duration_ms=duration_ms,
                ip_hash=hash_ip(get_client_ip(request)),
            )

        return response
