"""
Centralized logging configuration for spoo.me URL shortener.

This module sets up structured logging with:
- Environment-based configuration (dev vs production)
- JSON formatting for production, pretty console for development
- IP hashing for GDPR compliance in production
- Sentry integration for error tracking
- Sampling rate configuration for high-frequency events
"""

import os
import sys
import hashlib
import logging

import structlog
from structlog.types import EventDict, Processor


# Environment configuration
ENV = os.getenv("ENV", "development")
IS_PRODUCTION = ENV == "production"
IS_DEVELOPMENT = ENV == "development"

# Log level configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO" if IS_PRODUCTION else "DEBUG")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json" if IS_PRODUCTION else "console")

# Sampling rates for high-frequency events
SAMPLING_RATES = {
    "url_redirect": float(os.getenv("SAMPLE_RATE_REDIRECT", "0.05")),  # 5%
    "stats_query": float(os.getenv("SAMPLE_RATE_STATS", "0.20")),  # 20%
    "cache_operation": float(os.getenv("SAMPLE_RATE_CACHE", "0.01")),  # 1%
    "stats_export": float(os.getenv("SAMPLE_RATE_EXPORT", "0.80")),  # 80%
}

# Sensitive fields to redact from logs
REDACTED_FIELDS = {
    "password",
    "password_hash",
    "token",
    "api_key",
    "Authorization",
    "Cookie",
    "refresh_token",
    "access_token",
    "secret",
    "key",
}


def hash_ip(ip_address: str) -> str:
    """
    Hash IP address for privacy in production.

    In production, returns SHA-256 hash (first 16 chars) for GDPR compliance.
    In development, returns the original IP for easier debugging.

    Args:
        ip_address: The IP address to hash

    Returns:
        Hashed IP (production) or original IP (development)
    """
    if IS_PRODUCTION and ip_address:
        return hashlib.sha256(ip_address.encode()).hexdigest()[:16]
    return ip_address


def add_log_level(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add log level to event dict."""
    if method_name == "warn":
        method_name = "warning"
    event_dict["level"] = method_name
    return event_dict


def add_timestamp(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add ISO format timestamp to event dict."""
    from datetime import datetime, timezone

    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def redact_sensitive_fields(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Redact sensitive fields from logs."""
    for key in list(event_dict.keys()):
        if key.lower() in REDACTED_FIELDS or any(
            sensitive in key.lower()
            for sensitive in ["password", "token", "key", "secret"]
        ):
            if key not in ["level", "event", "timestamp", "logger"]:
                event_dict[key] = "***REDACTED***"
    return event_dict


def filter_exceptions(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Format exceptions properly for logging."""
    exc_info = event_dict.pop("exc_info", None)
    if exc_info:
        event_dict["exception"] = structlog.processors.format_exc_info(
            logger, method_name, {"exc_info": exc_info}
        )["exception"]
    return event_dict


def configure_structlog() -> None:
    """
    Configure structlog with appropriate processors for the environment.

    Production: JSON formatting for easy parsing
    Development: Pretty console formatting with colors
    """
    # Shared processors for all environments
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_timestamp,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        redact_sensitive_fields,
        filter_exceptions,
    ]

    if LOG_FORMAT == "json":
        # Production: JSON output
        structlog.configure(
            processors=shared_processors
            + [
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Development: Pretty console output with colors
        structlog.configure(
            processors=shared_processors
            + [
                structlog.processors.format_exc_info,
                structlog.dev.ConsoleRenderer(
                    colors=True,
                    pad_event=15,  # Reduced from default 30
                    sort_keys=False,  # Don't sort keys, keep order
                ),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )


def configure_stdlib_logging() -> None:
    """
    Configure standard library logging to work with structlog.

    Sets up:
    - Log level from environment
    - Console handler for stdout
    - Format compatible with structlog
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, LOG_LEVEL.upper()),
    )

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)

    # Silence pymongo debug logs (connection pool, server monitoring, etc.)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("pymongo.connection").setLevel(logging.WARNING)
    logging.getLogger("pymongo.serverSelection").setLevel(logging.WARNING)
    logging.getLogger("pymongo.command").setLevel(logging.WARNING)
    logging.getLogger("pymongo.topology").setLevel(logging.WARNING)


def configure_sentry_logging() -> None:
    """
    Configure Sentry integration for error tracking.

    If Sentry DSN is configured, this sets up:
    - Automatic error capture for ERROR+ level logs
    - Breadcrumbs for INFO+ level logs (context for errors)
    - User context attachment
    """
    sentry_dsn = os.getenv("SENTRY_DSN")

    if not sentry_dsn:
        return

    try:
        from sentry_sdk.integrations.logging import LoggingIntegration

        # Sentry logging integration
        # INFO+ logs become breadcrumbs (context)
        # ERROR+ logs become Sentry events
        sentry_logging = LoggingIntegration(  # noqa F841
            level=logging.INFO,  # Capture INFO and above as breadcrumbs
            event_level=logging.ERROR,  # Send ERROR and above as events
        )

        # Note: Sentry SDK initialization happens in main.py
        # This just configures how logging integrates with it

    except ImportError:
        # Sentry SDK not installed, skip configuration
        pass


def setup_logging() -> None:
    """
    Initialize logging system for the application.

    This is the main entry point for logging configuration.
    Should be called early in application startup (in main.py).
    """
    # Configure standard library logging first
    configure_stdlib_logging()

    # Configure structlog
    configure_structlog()

    # Configure Sentry integration if available
    configure_sentry_logging()

    # Log initialization
    logger = structlog.get_logger(__name__)
    logger.info(
        "logging_initialized",
        env=ENV,
        log_level=LOG_LEVEL,
        log_format=LOG_FORMAT,
        sentry_enabled=bool(os.getenv("SENTRY_DSN")),
    )


# Initialize logging when module is imported
setup_logging()
