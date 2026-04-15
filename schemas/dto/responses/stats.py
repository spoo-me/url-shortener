"""
Response DTO for the statistics endpoint.

StatsResponse — GET /api/v1/stats  (200)

The ``metrics`` dict has dynamic keys of the form ``{metric}_by_{dimension}``
(e.g. ``clicks_by_time``, ``unique_clicks_by_browser``), so it is typed as a
flexible dict rather than a rigid model.  The ``computed_metrics`` and
``time_bucket_info`` fields are added by the response formatter and may be absent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from schemas.dto.base import ResponseBase
from schemas.enums.stats import StatsScope


class StatsSummary(ResponseBase):
    """Summary statistics block inside StatsResponse."""

    total_clicks: int
    unique_clicks: int
    first_click: datetime | None = None
    last_click: datetime | None = None
    avg_redirection_time: float


class StatsTimeRange(ResponseBase):
    """Time range metadata inside StatsResponse."""

    start_date: datetime | None = None
    end_date: datetime | None = None


class ComputedMetrics(ResponseBase):
    """Optional computed metrics added by format_stats_response_with_metadata."""

    unique_click_rate: float
    repeat_click_rate: float
    average_clicks_per_visitor: float


class TimeBucketInfo(ResponseBase):
    """Time bucketing metadata — only present when 'time' is in group_by."""

    strategy: str  # e.g. "hourly", "daily", "weekly", "monthly", "legacy"
    mongo_format: str  # strftime format used in MongoDB $dateToString
    display_format: str  # strftime format used in the response labels
    timezone: str  # IANA timezone name
    interval_minutes: int | None = None  # only for fixed-interval strategies


class StatsResponse(ResponseBase):
    """Response body for GET /api/v1/stats.

    ``metrics`` uses dynamic keys ({metric}_by_{dimension}), each mapping to a
    list of data-point dicts.  Optional fields (``short_code``,
    ``time_bucket_info``, ``computed_metrics``) are absent when not applicable.
    """

    scope: StatsScope
    filters: dict[str, list[str]]
    group_by: list[str]
    timezone: str
    time_range: StatsTimeRange
    summary: StatsSummary
    # dynamic: {"clicks_by_time": [...], "unique_clicks_by_browser": [...], ...}
    metrics: dict[str, list[dict[str, Any]]] = Field(
        default_factory=dict,
        description=(
            "Keyed by '{metric}_by_{dimension}' (e.g. 'clicks_by_browser', "
            "'unique_clicks_by_time'). Each value is a list of data-point objects "
            "whose keys are the dimension name, the metric name, and "
            "'{metric}_percentage'."
        ),
    )

    # Metadata fields added by format_stats_response_with_metadata
    generated_at: datetime | None = None
    api_version: str | None = None

    # Only present when scope="anon"
    short_code: str | None = None

    # Only present when group_by includes "time"
    time_bucket_info: TimeBucketInfo | None = None

    # Only present when total_clicks > 0
    computed_metrics: ComputedMetrics | None = None
