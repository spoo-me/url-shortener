"""
Stats domain enums and allowed-value sets.

These are domain concepts used by services, strategies, export formatters,
and DTOs.  Extracted from ``schemas.dto.requests.stats`` so that service-layer
code does not depend on a request DTO module.
"""

from __future__ import annotations

from enum import Enum


class StatsScope(str, Enum):
    """Stats query scope."""

    ALL = "all"
    ANON = "anon"


class StatsDimension(str, Enum):
    """Stats group-by dimensions."""

    TIME = "time"
    BROWSER = "browser"
    OS = "os"
    COUNTRY = "country"
    CITY = "city"
    REFERRER = "referrer"
    SHORT_CODE = "short_code"


class StatsMetric(str, Enum):
    """Stats metric types."""

    CLICKS = "clicks"
    UNIQUE_CLICKS = "unique_clicks"


class ExportFormat(str, Enum):
    """Export file formats."""

    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    XML = "xml"


ALLOWED_SCOPES = frozenset(StatsScope)
ALLOWED_GROUP_BY = frozenset(StatsDimension)
ALLOWED_METRICS = frozenset(StatsMetric)
ALLOWED_FILTERS = frozenset(
    {
        StatsDimension.BROWSER,
        StatsDimension.OS,
        StatsDimension.COUNTRY,
        StatsDimension.CITY,
        StatsDimension.REFERRER,
        StatsDimension.SHORT_CODE,
    }
)
ALLOWED_EXPORT_FORMATS = frozenset(ExportFormat)
