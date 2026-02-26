"""
Response DTO for the statistics endpoint.

StatsResponse — GET /api/v1/stats  (200)

The ``metrics`` dict has dynamic keys of the form ``{metric}_by_{dimension}``
(e.g. ``clicks_by_time``, ``unique_clicks_by_browser``), so it is typed as a
flexible dict rather than a rigid model.  The ``computed_metrics`` and
``time_bucket_info`` fields are added by the response formatter and may be absent.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class StatsSummary(BaseModel):
    """Summary statistics block inside StatsResponse."""

    model_config = ConfigDict(populate_by_name=True)

    total_clicks: int
    unique_clicks: int
    first_click: Optional[str] = None  # ISO 8601 string or null
    last_click: Optional[str] = None  # ISO 8601 string or null
    avg_redirection_time: float


class StatsTimeRange(BaseModel):
    """Time range metadata inside StatsResponse."""

    model_config = ConfigDict(populate_by_name=True)

    start_date: Optional[str] = None  # ISO 8601 string
    end_date: Optional[str] = None  # ISO 8601 string


class ComputedMetrics(BaseModel):
    """Optional computed metrics added by format_stats_response_with_metadata."""

    model_config = ConfigDict(populate_by_name=True)

    unique_click_rate: float
    repeat_click_rate: float
    average_clicks_per_visitor: float


class StatsResponse(BaseModel):
    """Response body for GET /api/v1/stats.

    ``metrics`` uses dynamic keys ({metric}_by_{dimension}), each mapping to a
    list of data-point dicts.  Optional fields (``short_code``,
    ``time_bucket_info``, ``computed_metrics``) are absent when not applicable.
    """

    model_config = ConfigDict(populate_by_name=True)

    scope: str
    filters: dict[str, Any]
    group_by: list[str]
    timezone: str
    time_range: StatsTimeRange
    summary: StatsSummary
    # dynamic: {"clicks_by_time": [...], "unique_clicks_by_browser": [...], ...}
    metrics: dict[str, list[dict[str, Any]]]

    # Metadata fields added by format_stats_response_with_metadata
    generated_at: Optional[str] = None  # ISO 8601 string
    api_version: Optional[str] = None

    # Only present when scope="anon"
    short_code: Optional[str] = None

    # Only present when group_by includes "time"
    time_bucket_info: Optional[dict[str, Any]] = None

    # Only present when total_clicks > 0
    computed_metrics: Optional[ComputedMetrics] = None
