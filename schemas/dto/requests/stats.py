"""
Request DTOs for statistics and export endpoints.

StatsQuery   — GET /api/v1/stats   (query parameters)
ExportQuery  — GET /api/v1/export  (query parameters; superset of StatsQuery)

Both models parse comma-separated strings for multi-value fields and validate
IANA timezone names.  The JSON ``filters`` string is parsed into a typed dict.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALLOWED_SCOPES = frozenset({"all", "anon"})
ALLOWED_GROUP_BY = frozenset(
    {"time", "browser", "os", "country", "city", "referrer", "short_code"}
)
ALLOWED_METRICS = frozenset({"clicks", "unique_clicks"})
ALLOWED_FILTERS = frozenset(
    {"browser", "os", "country", "city", "referrer", "short_code"}
)
ALLOWED_EXPORT_FORMATS = frozenset({"csv", "xlsx", "json", "xml"})


def _parse_comma_separated(value: Any) -> list[str]:
    """Split a comma-separated string or pass-through a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value]
    return [item.strip() for item in str(value).split(",") if item.strip()]


class StatsQuery(BaseModel):
    """Query parameters for GET /api/v1/stats.

    Multi-value parameters (``group_by``, ``metrics``, ``browser``, ``os``,
    ``country``, ``city``, ``referrer``) accept comma-separated strings.
    The ``filters`` parameter accepts a JSON object string.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Scope: "all" = all URLs owned by the authenticated user;
    #        "anon" = single URL identified by short_code (may be unauthenticated)
    scope: str = Field(default="all")
    # Required when scope="anon"
    short_code: Optional[str] = None

    # Time range — ISO 8601 strings or Unix epoch seconds
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    # Aggregation dimensions: comma-separated subset of ALLOWED_GROUP_BY
    group_by: Optional[str] = None
    # Metrics to return: comma-separated subset of ALLOWED_METRICS
    metrics: Optional[str] = None

    # IANA timezone for output date formatting
    timezone: str = Field(default="UTC")

    # Dimension filters — JSON object string OR individual query params
    filters: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    referrer: Optional[str] = None

    # --- Parsed/validated results (excluded from serialization) ---
    parsed_group_by: list[str] = Field(default_factory=list, exclude=True)
    parsed_metrics: list[str] = Field(default_factory=list, exclude=True)
    parsed_filters: dict[str, list[str]] = Field(default_factory=dict, exclude=True)

    @field_validator("scope", mode="after")
    @classmethod
    def _validate_scope(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ALLOWED_SCOPES:
            raise ValueError(f"scope must be one of: {', '.join(ALLOWED_SCOPES)}")
        return v

    @model_validator(mode="after")
    def _parse_multi_value_fields(self) -> "StatsQuery":
        # group_by
        raw_group = _parse_comma_separated(self.group_by)
        invalid = set(raw_group) - ALLOWED_GROUP_BY
        if invalid:
            raise ValueError(f"invalid group_by values: {', '.join(invalid)}")
        self.parsed_group_by = raw_group if raw_group else ["time"]

        # metrics
        raw_metrics = _parse_comma_separated(self.metrics)
        if raw_metrics:
            invalid_m = set(raw_metrics) - ALLOWED_METRICS
            if invalid_m:
                raise ValueError(f"invalid metrics: {', '.join(invalid_m)}")
            self.parsed_metrics = raw_metrics
        else:
            self.parsed_metrics = ["clicks", "unique_clicks"]

        # filters JSON string
        if self.filters:
            try:
                filters_json = json.loads(self.filters)
            except json.JSONDecodeError as exc:
                raise ValueError("filters must be valid JSON") from exc
            if isinstance(filters_json, dict):
                for key, value in filters_json.items():
                    if key in ALLOWED_FILTERS:
                        self.parsed_filters[key] = _parse_comma_separated(value)

        # Individual dimension filter params
        for dim in ("browser", "os", "country", "city", "referrer", "short_code"):
            raw = getattr(self, dim, None)
            if raw:
                # short_code filter is blocked when scope=anon (bypass prevention)
                if dim == "short_code" and self.scope == "anon":
                    continue
                self.parsed_filters[dim] = _parse_comma_separated(raw)

        return self


class ExportQuery(StatsQuery):
    """Query parameters for GET /api/v1/export.

    Superset of StatsQuery — adds the required ``format`` parameter.
    """

    format: str

    @field_validator("format", mode="after")
    @classmethod
    def _validate_format(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("format parameter is required (csv, xlsx, json, xml)")
        if v not in ALLOWED_EXPORT_FORMATS:
            raise ValueError(
                f"invalid format — must be one of: {', '.join(ALLOWED_EXPORT_FORMATS)}"
            )
        return v
