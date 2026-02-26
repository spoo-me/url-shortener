"""
Date/time parsing and conversion utilities — framework-agnostic.

Consolidates three near-identical ``_parse_datetime`` copies found in
builders/stats.py, builders/query.py, and api/v1/keys.py into a single
canonical implementation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def parse_datetime(value: Any) -> Optional[datetime]:
    """Parse a date/time value into a timezone-aware UTC datetime.

    Accepts:
    - ``None`` → ``None``
    - ``int`` / ``float`` → treated as Unix epoch seconds
    - ``str`` ending in ``"Z"`` → converted to ``+00:00`` before parsing
    - Any ISO 8601 string (``datetime.fromisoformat``)

    Naive datetimes (no ``tzinfo``) are assumed to be UTC.

    Returns:
        A timezone-aware ``datetime`` in UTC, or ``None`` if *value* is ``None``
        or cannot be parsed.
    """
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        raw = str(value)
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def convert_to_gmt(expiration_time: str) -> Optional[datetime]:
    """Parse an ISO 8601 string and convert to UTC.

    Returns ``None`` for naive (timezone-unaware) strings because an
    expiration time without a timezone is ambiguous.

    Args:
        expiration_time: ISO 8601 datetime string (with or without tzinfo).

    Returns:
        UTC-aware ``datetime``, or ``None`` if the input is timezone-naive.
    """
    dt = datetime.fromisoformat(expiration_time)
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)
