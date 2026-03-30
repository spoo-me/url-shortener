"""
StatsService — analytics query orchestration.

Handles query building, $facet aggregation execution, and result formatting.
Framework-agnostic: no FastAPI imports.

The route layer is responsible for:
    - JWT/API key resolution → owner_id
    - API key scope verification (stats:read required)
    - Parsing StatsQuery DTO into individual typed values
    - HTTP response construction

This service receives already-parsed parameters and handles all business
logic from there, including date defaults, privacy checks, and the single
$facet MongoDB call.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, available_timezones

from bson import ObjectId

from errors import (
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from repositories.click_repository import ClickRepository
from repositories.url_repository import UrlRepository
from schemas.dto.requests.stats import StatsDimension, StatsMetric, StatsScope
from shared.aggregation_strategies import AggregationStrategyFactory
from shared.logging import get_logger

log = get_logger(__name__)

# Maximum allowed date range (days)
MAX_DATE_RANGE_DAYS = 90


class StatsService:
    """Analytics query service.

    Args:
        click_repo: Repository for the ``clicks`` time-series collection.
        url_repo:   Repository for the ``urlsV2`` collection (privacy checks).
    """

    def __init__(
        self,
        click_repo: ClickRepository,
        url_repo: UrlRepository,
    ) -> None:
        self._click_repo = click_repo
        self._url_repo = url_repo

    # ── Private: timezone helpers ─────────────────────────────────────────────

    @staticmethod
    def _to_user_tz(dt: datetime | None, tz_name: str) -> datetime | None:
        """Convert a UTC datetime to the user's timezone."""
        if dt is None:
            return None
        try:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(ZoneInfo(tz_name))
        except Exception as exc:
            log.warning(
                "timezone_conversion_failed",
                timezone=tz_name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return dt

    @staticmethod
    def _fmt_tz(dt: datetime | None, tz_name: str) -> datetime | None:
        """Convert a UTC datetime to the user's timezone."""
        return StatsService._to_user_tz(dt, tz_name)

    # ── Private: query building ───────────────────────────────────────────────

    @staticmethod
    def _build_click_query(
        scope: str,
        owner_id: str | None,
        short_code: str | None,
        start_date: datetime,
        end_date: datetime,
        filters: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Build the MongoDB $match query for the clicks collection.

        Preserves the exact filtering logic from utils/query_builder.py
        (ClickQueryBuilder + StatsQueryBuilderFactory), including:
        - meta.owner_id scoping for scope=all
        - meta.short_code scoping for scope=anon
        - Time range on clicked_at
        - Dimension filters with special handling for short_code and referrer/Direct
        """
        query: dict[str, Any] = {}

        # Scope filter
        if scope == StatsScope.ALL and owner_id:
            query["meta.owner_id"] = (
                ObjectId(owner_id) if isinstance(owner_id, str) else owner_id
            )
        elif scope == StatsScope.ANON and short_code:
            query["meta.short_code"] = short_code

        # Time range
        query["clicked_at"] = {"$gte": start_date, "$lte": end_date}

        # Dimension filters
        for dimension, values in filters.items():
            if not values:
                continue

            if dimension == StatsDimension.SHORT_CODE:
                # SECURITY: skip if scope already locks short_code (scope=anon)
                if "meta.short_code" in query:
                    log.warning(
                        "query_builder_scope_bypass_prevented",
                        dimension="short_code",
                        locked_short_code=query.get("meta.short_code"),
                        attempted_values=values,
                    )
                    continue
                query["meta.short_code"] = {"$in": values}
            elif dimension == StatsDimension.REFERRER:
                # "Direct" means null/missing referrer
                if "Direct" in values:
                    non_direct = [v for v in values if v != "Direct"]
                    if non_direct:
                        query["$or"] = [
                            {"referrer": {"$in": non_direct}},
                            {"referrer": {"$in": [None, ""]}},
                            {"referrer": {"$exists": False}},
                        ]
                    else:
                        query["$or"] = [
                            {"referrer": {"$in": [None, ""]}},
                            {"referrer": {"$exists": False}},
                        ]
                else:
                    query["referrer"] = {"$in": values}
            else:
                query[dimension] = {"$in": values}

        return query

    # ── Private: aggregation ──────────────────────────────────────────────────

    async def _execute_all_stats(
        self,
        query: dict[str, Any],
        group_by: list[str],
        start_date: datetime,
        end_date: datetime,
        tz_name: str,
    ) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
        """Execute summary + all dimension aggregations in ONE $facet DB call.

        This is critical for serverless (Vercel) where each DB round-trip adds
        ~200-400 ms of latency.  $facet runs all pipelines in parallel on the
        MongoDB server.

        Returns:
            (summary_stats, dimension_results)
        """
        # Build per-dimension strategies
        strategies: dict[str, Any] = {}
        for dim in group_by:
            if dim == StatsDimension.TIME:
                strategies[dim] = AggregationStrategyFactory.get(
                    dim,
                    start_date=start_date,
                    end_date=end_date,
                    timezone=tz_name,
                )
            else:
                strategies[dim] = AggregationStrategyFactory.get(dim)

        # $facet stages — each dimension aggregation skips the leading $match
        # because we apply $match once at the combined pipeline level.
        facet_stages: dict[str, Any] = {}

        # Summary facet: total clicks, unique IPs, first/last click, avg redirect
        facet_stages["_summary"] = [
            {
                "$group": {
                    "_id": None,
                    "total_clicks": {"$sum": 1},
                    "unique_clicks": {"$addToSet": "$ip_address"},
                    "first_click": {"$min": "$clicked_at"},
                    "last_click": {"$max": "$clicked_at"},
                    "avg_redirection_time": {"$avg": "$redirect_ms"},
                }
            },
            {"$addFields": {"unique_clicks": {"$size": "$unique_clicks"}}},
        ]

        for dim, strategy in strategies.items():
            full_pipeline = strategy.build_pipeline(query)
            # Strip the leading $match — we apply it once at the top
            facet_stages[dim] = full_pipeline[1:] if full_pipeline else []

        combined_pipeline = [
            {"$match": query},
            {"$facet": facet_stages},
        ]

        # Default empty summary
        summary: dict[str, Any] = {
            "total_clicks": 0,
            "unique_clicks": 0,
            "first_click": None,
            "last_click": None,
            "avg_redirection_time": 0,
        }
        results: dict[str, list[dict[str, Any]]] = {}

        try:
            raw = await self._click_repo.aggregate(combined_pipeline)

            if raw:
                facet_results = raw[0]

                # Extract summary
                summary_list = facet_results.get("_summary", [])
                if summary_list:
                    s = summary_list[0]
                    summary = {
                        "total_clicks": s.get("total_clicks", 0),
                        "unique_clicks": s.get("unique_clicks", 0),
                        "first_click": self._fmt_tz(s.get("first_click"), tz_name),
                        "last_click": self._fmt_tz(s.get("last_click"), tz_name),
                        "avg_redirection_time": round(
                            s.get("avg_redirection_time") or 0, 2
                        ),
                    }

                # Extract per-dimension results
                for dim, strategy in strategies.items():
                    results[dim] = strategy.format_results(facet_results.get(dim, []))
            else:
                for dim in group_by:
                    results[dim] = []

        except Exception as exc:
            log.error(
                "stats_facet_aggregation_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                dimensions=group_by,
            )
            for dim in group_by:
                results[dim] = []

        return summary, results

    # ── Private: response formatting ─────────────────────────────────────────

    def _format_results(
        self,
        scope: str,
        short_code: str | None,
        start_date: datetime,
        end_date: datetime,
        filters: dict[str, list[str]],
        group_by: list[str],
        metrics: list[str],
        tz_name: str,
        aggregation_results: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Format aggregation results into the API response structure.

        Preserves the exact shape from StatsQueryBuilder._format_results().
        """
        response: dict[str, Any] = {
            "scope": scope,
            "filters": filters,
            "group_by": group_by,
            "timezone": tz_name,
            "metrics": {},
        }

        if scope == StatsScope.ANON:
            response["short_code"] = short_code

        response["time_range"] = {
            "start_date": self._fmt_tz(start_date, tz_name),
            "end_date": self._fmt_tz(end_date, tz_name),
        }

        # Add time bucket info when time aggregation is requested
        if (
            StatsDimension.TIME in group_by
            and StatsDimension.TIME in aggregation_results
        ):
            try:
                time_strategy = AggregationStrategyFactory.get(
                    "time",
                    start_date=start_date,
                    end_date=end_date,
                    timezone=tz_name,
                )
                if hasattr(time_strategy, "get_bucket_info"):
                    response["time_bucket_info"] = time_strategy.get_bucket_info()
            except Exception as exc:
                log.warning(
                    "time_bucket_info_failed",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        # Build metrics dict
        for dim, dim_results in aggregation_results.items():
            for metric in metrics:
                result_key = "total_clicks" if metric == StatsMetric.CLICKS else metric
                metric_key = f"{metric}_by_{dim}"
                response["metrics"][metric_key] = []
                for result in dim_results:
                    if dim == StatsDimension.TIME:
                        dim_value = result.get("date", "unknown")
                    elif dim == StatsDimension.SHORT_CODE:
                        dim_value = result.get(
                            "short_code", result.get("alias", "unknown")
                        )
                    else:
                        dim_value = result.get(dim, "unknown")
                    response["metrics"][metric_key].append(
                        {dim: dim_value, metric: result.get(result_key, 0)}
                    )

        return response

    @staticmethod
    def _add_metadata(response: dict[str, Any]) -> dict[str, Any]:
        """Enhance the response with metadata and computed percentages.

        Preserves the exact logic from utils/stats_utils.format_stats_response_with_metadata().
        """
        response = response.copy()

        response["generated_at"] = datetime.now(timezone.utc)
        response["api_version"] = "v1"

        summary = response.get("summary", {})
        if summary:
            total_clicks = summary.get("total_clicks", 0)
            unique_clicks = summary.get("unique_clicks", 0)
            if total_clicks > 0:
                unique_rate = (unique_clicks / total_clicks) * 100
                response["computed_metrics"] = {
                    "unique_click_rate": round(unique_rate, 2),
                    "repeat_click_rate": round(100 - unique_rate, 2),
                    "average_clicks_per_visitor": round(
                        total_clicks / unique_clicks if unique_clicks > 0 else 0, 2
                    ),
                }

        # Add percentage fields to each metric dimension
        metrics = response.get("metrics", {})
        for _metric_key, metric_data in metrics.items():
            if isinstance(metric_data, list) and metric_data:
                total = sum(
                    item.get(list(item.keys())[-1], 0)
                    for item in metric_data
                    if isinstance(item, dict)
                )
                if total > 0:
                    for item in metric_data:
                        if isinstance(item, dict):
                            value_key = list(item.keys())[-1]
                            value = item.get(value_key, 0)
                            item[f"{value_key}_percentage"] = round(
                                (value / total) * 100, 2
                            )

        return response

    # ── Public API ────────────────────────────────────────────────────────────

    async def query(
        self,
        owner_id: str | None,
        scope: str,
        short_code: str | None,
        start_date: datetime | None,
        end_date: datetime | None,
        filters: dict[str, list[str]],
        group_by: list[str],
        metrics: list[str],
        tz_name: str,
    ) -> dict[str, Any]:
        """Execute a stats query and return the formatted, enhanced response.

        Args:
            owner_id:   String user ID for scope=all, or None.
            scope:      ``"all"`` | ``"anon"``
            short_code: Required when scope=anon.
            start_date: UTC start of the time window (None → 7 days ago).
            end_date:   UTC end of the time window (None → now).
            filters:    Dimension filter dict, e.g. ``{"browser": ["Chrome"]}``.
            group_by:   Aggregation dimensions, e.g. ``["time", "browser"]``.
            metrics:    Metrics to return, e.g. ``["clicks", "unique_clicks"]``.
            tz_name:    IANA timezone name for output formatting.

        Returns:
            Formatted stats dict ready for JSON serialisation.

        Raises:
            ValidationError:      Invalid scope/target parameters.
            NotFoundError:        short_code not found (scope=anon).
            AuthenticationError:  Auth required for private stats or scope=all.
            ForbiddenError:       Authenticated user does not own private URL.
            AppError:             DB failure.
        """
        start_time = time.perf_counter()

        # ── Apply date defaults ───────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        if start_date is None and end_date is None:
            end_date = now
            start_date = now - timedelta(days=7)
        elif start_date is None:
            start_date = end_date - timedelta(days=7)
        elif end_date is None:
            end_date = now

        # Cap future dates to now
        if start_date > now:
            start_date = now
        if end_date > now:
            end_date = now

        # ── Date range validation ─────────────────────────────────────────────
        if start_date > end_date:
            raise ValidationError("start_date must be before end_date")
        if (end_date - start_date).days > MAX_DATE_RANGE_DAYS:
            raise ValidationError(
                f"date range cannot exceed {MAX_DATE_RANGE_DAYS} days"
            )

        # ── Validate timezone ─────────────────────────────────────────────────
        timezone_aliases = {
            "Asia/Calcutta": "Asia/Kolkata",
            "Asia/Katmandu": "Asia/Kathmandu",
            "Asia/Rangoon": "Asia/Yangon",
            "Asia/Saigon": "Asia/Ho_Chi_Minh",
            "US/Eastern": "America/New_York",
            "US/Central": "America/Chicago",
            "US/Mountain": "America/Denver",
            "US/Pacific": "America/Los_Angeles",
        }
        tz_name = timezone_aliases.get(tz_name, tz_name)
        if tz_name not in available_timezones():
            log.warning("invalid_timezone_provided", timezone=tz_name, fallback="UTC")
            tz_name = "UTC"

        # ── Scope/target validation ───────────────────────────────────────────
        if scope == StatsScope.ANON:
            if not short_code:
                raise ValidationError("short_code is required when scope=anon")

            privacy = await self._url_repo.check_stats_privacy(short_code)
            if not privacy["exists"]:
                raise NotFoundError("short_code not found")

            if privacy["private"]:
                if owner_id is None:
                    log.warning(
                        "stats_access_denied",
                        reason="unauthenticated_private_stats",
                        short_code=short_code,
                    )
                    raise AuthenticationError(
                        "this URL has private statistics - authentication required"
                    )
                if privacy["owner_id"] != str(owner_id):
                    log.warning(
                        "stats_access_denied",
                        reason="not_owner",
                        short_code=short_code,
                        requesting_user=str(owner_id),
                        owner_user=privacy["owner_id"],
                    )
                    raise ForbiddenError("access denied - private statistics")

        elif scope == StatsScope.ALL:
            if owner_id is None:
                log.warning(
                    "stats_access_denied",
                    reason="unauthenticated_scope_all",
                )
                raise AuthenticationError("authentication required for scope=all")

        # ── Execute ───────────────────────────────────────────────────────────
        click_query = self._build_click_query(
            scope, owner_id, short_code, start_date, end_date, filters
        )
        summary, aggregation_results = await self._execute_all_stats(
            click_query, group_by, start_date, end_date, tz_name
        )

        # ── Format ────────────────────────────────────────────────────────────
        response = self._format_results(
            scope,
            short_code,
            start_date,
            end_date,
            filters,
            group_by,
            metrics,
            tz_name,
            aggregation_results,
        )
        response["summary"] = summary
        response = self._add_metadata(response)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        log.info(
            "stats_query",
            scope=scope,
            short_code=short_code if scope == StatsScope.ANON else None,
            group_by=group_by,
            metrics=metrics,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            filter_count=len(filters),
            total_clicks=summary.get("total_clicks", 0),
            unique_clicks=summary.get("unique_clicks", 0),
            duration_ms=duration_ms,
        )

        return response
