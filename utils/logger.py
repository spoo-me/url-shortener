"""
Logger factory and utility functions for spoo.me URL shortener.

Provides:
- get_logger(): Get a configured logger instance
- should_sample(): Determine if an event should be logged based on sampling rate
- hash_ip(): Hash IP addresses for privacy
"""

import random
from typing import Optional

import structlog
from structlog.stdlib import BoundLogger

from .logging_config import SAMPLING_RATES, hash_ip as _hash_ip


def get_logger(name: str) -> BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Configured structlog BoundLogger instance

    Example:
        >>> from utils.logger import get_logger
        >>> log = get_logger(__name__)
        >>> log.info("user_login", user_id="123", method="password")
    """
    return structlog.get_logger(name)


def should_sample(event_type: str) -> bool:
    """
    Determine if an event should be logged based on sampling rate.

    Uses random sampling to reduce log volume for high-frequency events.
    Sampling rates are configured in logging_config.py and can be overridden
    via environment variables.

    Args:
        event_type: Type of event (e.g., "url_redirect", "stats_query")

    Returns:
        True if the event should be logged, False otherwise

    Example:
        >>> from utils.logger import get_logger, should_sample
        >>> log = get_logger(__name__)
        >>> if should_sample("url_redirect"):
        ...     log.info("url_redirect", short_code="abc123")
    """
    # Get sampling rate for this event type (default to 100% if not configured)
    sample_rate = SAMPLING_RATES.get(event_type, 1.0)

    # Always log if rate is 1.0 (100%)
    if sample_rate >= 1.0:
        return True

    # Never log if rate is 0.0 (0%)
    if sample_rate <= 0.0:
        return False

    # Probabilistic sampling
    return random.random() < sample_rate


def hash_ip(ip_address: Optional[str]) -> Optional[str]:
    """
    Hash IP address for privacy in production.

    This is a convenience wrapper around logging_config.hash_ip()
    that handles None values gracefully.

    In production: Returns SHA-256 hash (first 16 chars) for GDPR compliance
    In development: Returns the original IP for easier debugging

    Args:
        ip_address: The IP address to hash (can be None)

    Returns:
        Hashed IP (production), original IP (development), or None

    Example:
        >>> from utils.logger import get_logger, hash_ip
        >>> log = get_logger(__name__)
        >>> log.warning("suspicious_activity", ip_hash=hash_ip(client_ip))
    """
    if ip_address is None:
        return None
    return _hash_ip(ip_address)


def log_with_context(logger: BoundLogger, **context) -> BoundLogger:
    """
    Bind context to a logger for all subsequent log calls.

    Useful for adding common context (like user_id, request_id) that
    will be included in all logs within a scope.

    Args:
        logger: The logger to bind context to
        **context: Key-value pairs to bind

    Returns:
        Logger with bound context

    Example:
        >>> from utils.logger import get_logger, log_with_context
        >>> log = get_logger(__name__)
        >>> log = log_with_context(log, user_id="123", request_id="req_abc")
        >>> log.info("user_action")  # Will include user_id and request_id
    """
    return logger.bind(**context)
