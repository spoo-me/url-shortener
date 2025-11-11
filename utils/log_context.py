"""
Flask middleware for automatic request logging and context management.

Provides:
- Automatic request ID generation for correlation
- Request/response logging with timing
- User context binding (user_id, ip, etc.)
- Context available throughout request lifecycle
"""

import time
import uuid
from functools import wraps
from typing import Optional

import structlog
from flask import Flask, request, g
from werkzeug.exceptions import HTTPException

from .logger import get_logger, hash_ip


def generate_request_id() -> str:
    """Generate a unique request ID for correlation."""
    return f"req_{uuid.uuid4().hex[:12]}"


def get_user_context() -> dict:
    """
    Extract user context from Flask g object.

    Returns:
        Dictionary with user_id and auth_method if available
    """
    context = {}

    # Get user_id from g object (set by @requires_auth decorator)
    if hasattr(g, "user_id") and g.user_id:
        context["user_id"] = str(g.user_id)

    # Get auth method from JWT claims
    if hasattr(g, "jwt_claims") and g.jwt_claims:
        amr = g.jwt_claims.get("amr", [])
        if amr:
            context["auth_method"] = amr[0] if isinstance(amr, list) else amr

    # Check if request is using API key
    if hasattr(g, "api_key") and g.api_key:
        context["auth_method"] = "api_key"
        context["api_key_prefix"] = g.api_key.get("token_prefix")

    return context


def log_request_start(log: structlog.stdlib.BoundLogger) -> None:
    """Log the start of a request with context."""
    # Only log request start for non-redirect endpoints in production
    # (to reduce noise from high-frequency redirects)
    from .logging_config import IS_PRODUCTION

    if IS_PRODUCTION and not request.path.startswith("/api/"):
        return

    log.debug(
        "request_started",
        method=request.method,
        path=request.path,
        query_string=request.query_string.decode() if request.query_string else None,
    )


def log_request_end(
    log: structlog.stdlib.BoundLogger,
    status_code: int,
    duration_ms: int,
) -> None:
    """Log the end of a request with timing and status."""
    # Determine log level based on status code
    if status_code >= 500:
        log_fn = log.error
    elif status_code >= 400:
        log_fn = log.warning
    else:
        log_fn = log.info

    log_fn(
        "request_completed",
        method=request.method,
        path=request.path,
        status_code=status_code,
        duration_ms=duration_ms,
    )


def setup_logging_middleware(app: Flask) -> None:
    """
    Register logging middleware with Flask app.

    This sets up:
    - Request ID generation
    - User context binding
    - Automatic request/response logging
    - Context available via g.log throughout request

    Args:
        app: Flask application instance

    Example:
        >>> from flask import Flask
        >>> from utils.log_context import setup_logging_middleware
        >>> app = Flask(__name__)
        >>> setup_logging_middleware(app)
    """

    @app.before_request
    def before_request():
        """Setup logging context before each request."""
        # Record start time for duration calculation
        g.request_start_time = time.time()

        # Generate unique request ID
        request_id = generate_request_id()
        g.request_id = request_id

        # Get client IP (handles proxy headers)
        from utils.url_utils import get_client_ip

        client_ip = get_client_ip()

        # Create base logger with request context
        log = get_logger("spoo.request")
        log = log.bind(
            request_id=request_id,
            method=request.method,
            path=request.path,
            ip_hash=hash_ip(client_ip),
            user_agent=request.headers.get("User-Agent", "")[:100],  # Truncate
        )

        # Add user context if available
        user_context = get_user_context()
        if user_context:
            log = log.bind(**user_context)

        # Store logger in g for use throughout request
        g.log = log

        # Log request start
        log_request_start(log)

    @app.after_request
    def after_request(response):
        """Log request completion after response is ready."""
        if not hasattr(g, "log") or not hasattr(g, "request_start_time"):
            return response

        # Calculate request duration
        duration_ms = int((time.time() - g.request_start_time) * 1000)

        # Log request completion
        log_request_end(g.log, response.status_code, duration_ms)

        # Add request ID to response headers for debugging
        response.headers["X-Request-ID"] = g.request_id

        return response

    @app.teardown_request
    def teardown_request(exc: Optional[Exception] = None):
        """Handle any exceptions that occurred during request."""
        if exc and not isinstance(exc, HTTPException):
            # Log unhandled exceptions
            if hasattr(g, "log"):
                g.log.error(
                    "unhandled_exception",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    exc_info=exc,
                )
