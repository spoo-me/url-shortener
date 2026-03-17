"""
Request DTOs for statistics and export endpoints.

StatsQuery   — GET /api/v1/stats   (query parameters)
ExportQuery  — GET /api/v1/export  (query parameters; superset of StatsQuery)

Both models parse comma-separated strings for multi-value fields and validate
IANA timezone names.  The JSON ``filters`` string is parsed into a typed dict.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

from schemas.dto.requests._descriptions import (
    STATS_BROWSER_DESC,
    STATS_CITY_DESC,
    STATS_COUNTRY_DESC,
    STATS_END_DATE_DESC,
    STATS_FILTERS_DESC,
    STATS_GROUP_BY_DESC,
    STATS_METRICS_DESC,
    STATS_OS_DESC,
    STATS_REFERRER_DESC,
    STATS_SCOPE_DESC,
    STATS_SHORT_CODE_DESC,
    STATS_START_DATE_DESC,
    STATS_TIMEZONE_DESC,
)

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

    scope: Literal["all", "anon"] = Field(default="all", description=STATS_SCOPE_DESC)
    short_code: Optional[str] = Field(
        default=None,
        description=STATS_SHORT_CODE_DESC,
        examples=["mylink"],
    )

    start_date: Optional[str] = Field(
        default=None,
        description=STATS_START_DATE_DESC,
        examples=["2025-01-01T00:00:00Z"],
    )
    end_date: Optional[str] = Field(
        default=None,
        description=STATS_END_DATE_DESC,
        examples=["2025-12-31T23:59:59Z"],
    )

    group_by: Optional[str] = Field(
        default=None,
        description=STATS_GROUP_BY_DESC,
        examples=["time,browser", "country", "time,country,browser"],
    )
    metrics: Optional[str] = Field(
        default=None,
        description=STATS_METRICS_DESC,
        examples=["clicks,unique_clicks", "clicks"],
    )

    timezone: str = Field(
        default="UTC",
        description=STATS_TIMEZONE_DESC,
        examples=["UTC", "America/New_York"],
    )

    filters: Optional[str] = Field(
        default=None,
        description=STATS_FILTERS_DESC,
        examples=[
            '{"browser":["Chrome","Firefox"]}',
            '{"country":["United States","Canada"],"browser":["Chrome"]}',
        ],
    )
    browser: Optional[str] = Field(
        default=None, description=STATS_BROWSER_DESC, examples=["Chrome,Firefox"]
    )
    os: Optional[str] = Field(
        default=None, description=STATS_OS_DESC, examples=["Windows,macOS"]
    )
    country: Optional[str] = Field(
        default=None, description=STATS_COUNTRY_DESC, examples=["United States,Germany"]
    )
    city: Optional[str] = Field(
        default=None, description=STATS_CITY_DESC, examples=["San Francisco,Berlin"]
    )
    referrer: Optional[str] = Field(
        default=None,
        description=STATS_REFERRER_DESC,
        examples=["https://google.com,https://twitter.com"],
    )

    # --- Parsed/validated results (private — not exposed as query params) ---
    _parsed_group_by: list[str] = PrivateAttr(default_factory=list)
    _parsed_metrics: list[str] = PrivateAttr(default_factory=list)
    _parsed_filters: dict[str, list[str]] = PrivateAttr(default_factory=dict)

    @property
    def parsed_group_by(self) -> list[str]:
        return self._parsed_group_by

    @property
    def parsed_metrics(self) -> list[str]:
        return self._parsed_metrics

    @property
    def parsed_filters(self) -> dict[str, list[str]]:
        return self._parsed_filters

    @field_validator("scope", mode="before")
    @classmethod
    def _normalize_scope(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _parse_multi_value_fields(self) -> "StatsQuery":
        # group_by
        raw_group = _parse_comma_separated(self.group_by)
        invalid = set(raw_group) - ALLOWED_GROUP_BY
        if invalid:
            raise ValueError(f"invalid group_by values: {', '.join(invalid)}")
        self._parsed_group_by = raw_group if raw_group else ["time"]

        # metrics
        raw_metrics = _parse_comma_separated(self.metrics)
        if raw_metrics:
            invalid_m = set(raw_metrics) - ALLOWED_METRICS
            if invalid_m:
                raise ValueError(f"invalid metrics: {', '.join(invalid_m)}")
            self._parsed_metrics = raw_metrics
        else:
            self._parsed_metrics = ["clicks", "unique_clicks"]

        # filters JSON string
        parsed_filters: dict[str, list[str]] = {}
        if self.filters:
            try:
                filters_json = json.loads(self.filters)
            except json.JSONDecodeError as exc:
                raise ValueError("filters must be valid JSON") from exc
            if isinstance(filters_json, dict):
                for key, value in filters_json.items():
                    if key in ALLOWED_FILTERS:
                        parsed_filters[key] = _parse_comma_separated(value)

        # Individual dimension filter params
        for dim in ("browser", "os", "country", "city", "referrer", "short_code"):
            raw = getattr(self, dim, None)
            if raw:
                # short_code filter is blocked when scope=anon (bypass prevention)
                if dim == "short_code" and self.scope == "anon":
                    continue
                parsed_filters[dim] = _parse_comma_separated(raw)

        self._parsed_filters = parsed_filters

        return self


class ExportQuery(StatsQuery):
    """Query parameters for GET /api/v1/export.

    Superset of StatsQuery — adds the required ``format`` parameter.
    """

    format: Literal["csv", "xlsx", "json", "xml"] = Field(
        description="Export file format.",
    )

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
