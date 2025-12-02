from flask import request, jsonify, Response
from datetime import datetime, timezone, timedelta
import json
from typing import Optional, Any, List, Dict
from zoneinfo import ZoneInfo, available_timezones

from utils.mongo_utils import (
    clicks_collection,
    check_url_stats_privacy,
)
from utils.aggregation_strategies import AggregationStrategyFactory
from utils.query_builder import StatsQueryBuilderFactory
from utils.stats_utils import format_stats_response_with_metadata, validate_date_range
from utils.logger import get_logger, should_sample

log = get_logger(__name__)


class StatsQueryBuilder:
    """Builder for querying URL statistics with filtering, grouping, and aggregation"""

    def __init__(self, owner_id, args: dict[str, Any]):
        self.owner_id = owner_id
        self.args = args
        self.error: Optional[tuple[Response, int]] = None

        # Query parameters
        self.scope: str = "all"  # "all" | "anon"
        self.short_code: Optional[str] = None
        self.start_date: Optional[datetime] = None
        self.end_date: Optional[datetime] = None
        self.filters: Dict[str, List[str]] = {}
        self.group_by: List[str] = []
        self.metrics: List[str] = ["clicks", "unique_clicks"]
        self.timezone: str = "UTC"  # IANA timezone for output formatting

        # Allowed values
        self.allowed_scopes = {"all", "anon"}
        self.allowed_group_by = {
            "time",
            "browser",
            "os",
            # "device",  # DISABLED: Reliable device detection not available yet
            "country",
            "city",
            "referrer",
            "short_code",
        }
        self.allowed_metrics = {"clicks", "unique_clicks"}
        # Allowed dimensions for filtering statistics
        # TODO: "device" is disabled until reliable device detection is implemented
        self.allowed_filters = {
            "browser",
            "os",
            "country",
            "city",
            "referrer",
            "short_code",
        }

    def _fail(self, body: dict, status: int) -> "StatsQueryBuilder":
        self.error = (jsonify(body), status)
        return self

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
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
        except Exception:
            return None

    def _parse_comma_separated(self, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value]
        return [item.strip() for item in str(value).split(",") if item.strip()]

    def _convert_datetime_to_timezone(
        self, dt: Optional[datetime]
    ) -> Optional[datetime]:
        """Convert UTC datetime to user's timezone for output"""
        if dt is None:
            return None
        try:
            # Ensure datetime is in UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            # Convert to user's timezone
            user_tz = ZoneInfo(self.timezone)
            return dt.astimezone(user_tz)
        except Exception as e:
            log.warning(
                "timezone_conversion_failed",
                timezone=self.timezone,
                error=str(e),
                error_type=type(e).__name__,
            )
            return dt  # Return original if conversion fails

    def _format_datetime_in_timezone(self, dt: Optional[datetime]) -> Optional[str]:
        """Format datetime as ISO string in user's timezone"""
        converted = self._convert_datetime_to_timezone(dt)
        return converted.isoformat() if converted else None

    def parse_auth_scope(self) -> "StatsQueryBuilder":
        api_key_doc = getattr(request, "api_key", None)
        if api_key_doc is not None:
            scopes = set(api_key_doc.get("scopes", []))
            if "admin:all" not in scopes and "stats:read" not in scopes:
                log.warning(
                    "stats_access_denied",
                    reason="missing_scope",
                    required_scope="stats:read",
                    api_key_scopes=list(scopes),
                )
                return self._fail(
                    {"error": "api key lacks required scope: stats:read"}, 403
                )
        return self

    def parse_scope_and_target(self) -> "StatsQueryBuilder":
        self.scope = self.args.get("scope", "all").strip().lower()
        if self.scope not in self.allowed_scopes:
            return self._fail(
                {"error": f"scope must be one of: {', '.join(self.allowed_scopes)}"},
                400,
            )

        if self.scope == "anon":
            self.short_code = self.args.get("short_code", "").strip()
            if not self.short_code:
                return self._fail(
                    {"error": "short_code is required when scope=anon"}, 400
                )

            # Check URL privacy settings
            privacy_info = check_url_stats_privacy(self.short_code)
            if not privacy_info["exists"]:
                return self._fail({"error": "short_code not found"}, 404)

            # If stats are private, only allow access if user owns the URL
            if privacy_info["private"]:
                if self.owner_id is None:
                    log.warning(
                        "stats_access_denied",
                        reason="unauthenticated_private_stats",
                        short_code=self.short_code,
                    )
                    return self._fail(
                        {
                            "error": "this URL has private statistics - authentication required"
                        },
                        401,
                    )

                # Check if authenticated user owns this URL
                if privacy_info["owner_id"] != str(self.owner_id):
                    log.warning(
                        "stats_access_denied",
                        reason="not_owner",
                        short_code=self.short_code,
                        requesting_user=str(self.owner_id),
                        owner_user=privacy_info["owner_id"],
                    )
                    return self._fail(
                        {"error": "access denied - private statistics"}, 403
                    )

        elif self.scope == "all":
            if self.owner_id is None:
                log.warning(
                    "stats_access_denied",
                    reason="unauthenticated_scope_all",
                    scope="all",
                )
                return self._fail(
                    {"error": "authentication required for scope=all"}, 401
                )

        return self

    def parse_time_range(self) -> "StatsQueryBuilder":
        self.start_date = self._parse_datetime(self.args.get("start_date"))
        self.end_date = self._parse_datetime(self.args.get("end_date"))

        # Set default values if not provided
        now = datetime.now(timezone.utc)
        if self.start_date is None and self.end_date is None:
            # Default: end_date is now, start_date is 7 days ago
            self.end_date = now
            self.start_date = now - timedelta(days=7)
        elif self.start_date is None and self.end_date is not None:
            # If only end_date provided, set start_date to 7 days before end_date
            self.start_date = self.end_date - timedelta(days=7)
        elif self.start_date is not None and self.end_date is None:
            # If only start_date provided, set end_date to now
            self.end_date = now

        # Cap future dates to current time to handle timing differences
        if self.start_date and self.start_date > now:
            self.start_date = now
        if self.end_date and self.end_date > now:
            self.end_date = now

        # Validate date range
        validation = validate_date_range(self.start_date, self.end_date)
        if not validation["is_valid"]:
            log.info(
                "stats_date_range_invalid",
                start_date=self.start_date.isoformat() if self.start_date else None,
                end_date=self.end_date.isoformat() if self.end_date else None,
                error=validation["error"],
            )
            return self._fail({"error": validation["error"]}, 400)

        return self

    def parse_filters(self) -> "StatsQueryBuilder":
        # Parse JSON filters
        filter_raw = self.args.get("filters")
        if filter_raw:
            try:
                filters_json = json.loads(filter_raw)
                if isinstance(filters_json, dict):
                    for key, value in filters_json.items():
                        if key in self.allowed_filters:
                            self.filters[key] = self._parse_comma_separated(value)
            except json.JSONDecodeError:
                return self._fail({"error": "filters must be valid JSON"}, 400)

        # Parse individual filter parameters
        for filter_name in self.allowed_filters:
            filter_value = self.args.get(filter_name)
            if filter_value:
                # Skip short_code parameter when scope=anon (it's the scope param, not a filter)
                if filter_name == "short_code" and self.scope == "anon":
                    continue
                self.filters[filter_name] = self._parse_comma_separated(filter_value)

        # SECURITY: Prevent filter-based scope bypass
        # In scope=anon, the short_code is already locked by the scope parameter
        # Allowing short_code filter would let users bypass privacy checks
        if self.scope == "anon" and "short_code" in self.filters:
            log.warning(
                "stats_scope_bypass_attempt",
                short_code=self.short_code,
                attempted_filter=self.filters.get("short_code"),
                user_id=str(self.owner_id) if self.owner_id else None,
            )
            return self._fail(
                {
                    "error": "short_code filter not allowed with scope=anon - short_code is already specified"
                },
                400,
            )

        return self

    def parse_group_by(self) -> "StatsQueryBuilder":
        group_by_raw = self.args.get("group_by", "")
        self.group_by = self._parse_comma_separated(group_by_raw)

        # Validate group_by values
        invalid_groups = set(self.group_by) - self.allowed_group_by
        if invalid_groups:
            return self._fail(
                {"error": f"invalid group_by values: {', '.join(invalid_groups)}"}, 400
            )

        # Default to time if no group_by specified
        if not self.group_by:
            self.group_by = ["time"]

        return self

    def parse_metrics(self) -> "StatsQueryBuilder":
        metrics_raw = self.args.get("metrics", "")
        if metrics_raw:
            self.metrics = self._parse_comma_separated(metrics_raw)

        # Validate metrics
        invalid_metrics = set(self.metrics) - self.allowed_metrics
        if invalid_metrics:
            return self._fail(
                {"error": f"invalid metrics: {', '.join(invalid_metrics)}"}, 400
            )

        return self

    def parse_timezone(self) -> "StatsQueryBuilder":
        """Parse and validate timezone parameter for output formatting"""
        timezone_raw = self.args.get("timezone", "UTC").strip()

        # Map of legacy/deprecated timezone names to current IANA names
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

        # Check if it's an alias and convert to canonical name
        if timezone_raw in timezone_aliases:
            timezone_raw = timezone_aliases[timezone_raw]

        # Validate timezone - fallback to UTC if invalid
        if timezone_raw not in available_timezones():
            log.warning(
                "invalid_timezone_provided", timezone=timezone_raw, fallback="UTC"
            )
            self.timezone = "UTC"
        else:
            self.timezone = timezone_raw

        return self

    def _build_click_query(self) -> Dict[str, Any]:
        """Build MongoDB query for clicks collection using builder pattern"""
        try:
            # Use the appropriate factory method based on scope
            if self.scope == "all":
                builder = StatsQueryBuilderFactory.for_user_stats(
                    str(self.owner_id), self.start_date, self.end_date
                )
            elif self.scope == "anon":
                builder = StatsQueryBuilderFactory.for_anonymous_stats(
                    self.short_code, self.start_date, self.end_date
                )
            else:
                return self._fail({"error": "invalid scope"}, 400)

            # Add dimension filters
            builder.with_filters(self.filters)

            return builder.build()

        except Exception as e:
            log.error(
                "stats_query_build_failed",
                scope=self.scope,
                error=str(e),
                error_type=type(e).__name__,
            )
            self._fail({"error": "failed to build query"}, 500)
            return None

    def _execute_all_stats(
        self, query: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
        """
        Execute ALL stats (summary + aggregations) in a SINGLE MongoDB round-trip using $facet.

        This is critical for serverless (Vercel) where each DB call adds ~200-400ms latency.
        $facet allows running multiple aggregation pipelines in parallel on the server side.

        Returns:
            tuple: (summary_stats, aggregation_results)
        """
        results = {}

        # Build strategies for each dimension
        strategies = {}
        for group_dimension in self.group_by:
            if group_dimension == "time":
                strategies[group_dimension] = AggregationStrategyFactory.get(
                    group_dimension,
                    start_date=self.start_date,
                    end_date=self.end_date,
                    timezone=self.timezone,
                )
            else:
                strategies[group_dimension] = AggregationStrategyFactory.get(
                    group_dimension
                )

        # Build $facet pipeline - all aggregations in ONE query
        facet_stages = {}

        # Add summary stats as a facet
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

        # Add dimension aggregations
        for dimension, strategy in strategies.items():
            # Get the pipeline stages AFTER $match (we'll do $match once at the start)
            full_pipeline = strategy.build_pipeline(query)
            # Skip the $match stage (index 0), keep the rest
            facet_stages[dimension] = full_pipeline[1:] if full_pipeline else []

        # Single aggregation with $facet - ONE DB CALL for everything
        combined_pipeline = [
            {"$match": query},
            {"$facet": facet_stages},
        ]

        # Default empty summary
        summary = {
            "total_clicks": 0,
            "unique_clicks": 0,
            "first_click": None,
            "last_click": None,
            "avg_redirection_time": 0,
        }

        try:
            raw_results = list(clicks_collection.aggregate(combined_pipeline))

            if raw_results:
                facet_results = raw_results[0]

                # Extract summary
                summary_results = facet_results.get("_summary", [])
                if summary_results:
                    s = summary_results[0]
                    summary = {
                        "total_clicks": s.get("total_clicks", 0),
                        "unique_clicks": s.get("unique_clicks", 0),
                        "first_click": self._format_datetime_in_timezone(
                            s.get("first_click")
                        ),
                        "last_click": self._format_datetime_in_timezone(
                            s.get("last_click")
                        ),
                        "avg_redirection_time": round(
                            s.get("avg_redirection_time") or 0, 2
                        ),
                    }

                # Extract dimension aggregations
                for dimension, strategy in strategies.items():
                    dimension_results = facet_results.get(dimension, [])
                    results[dimension] = strategy.format_results(dimension_results)
            else:
                # No results, initialize empty
                for dimension in self.group_by:
                    results[dimension] = []

        except Exception as e:
            log.error(
                "stats_facet_aggregation_failed",
                error=str(e),
                error_type=type(e).__name__,
                dimensions=self.group_by,
                query=query,
            )
            # Fallback to empty results
            for dimension in self.group_by:
                results[dimension] = []

        return summary, results

    def _format_results(
        self, aggregation_results: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Format aggregation results into response structure"""
        response = {
            "scope": self.scope,
            "filters": self.filters,
            "group_by": self.group_by,
            "timezone": self.timezone,  # Include timezone in response
            "metrics": {},
        }

        # Add scope-specific metadata
        if self.scope == "anon":
            response["short_code"] = self.short_code

        # Add time range (always present now due to defaults) - converted to user timezone
        response["time_range"] = {
            "start_date": self._format_datetime_in_timezone(self.start_date),
            "end_date": self._format_datetime_in_timezone(self.end_date),
        }

        # Add time bucketing information if time aggregation is used
        if "time" in self.group_by and "time" in aggregation_results:
            try:
                # Create a temporary strategy to get bucket info
                time_strategy = AggregationStrategyFactory.get(
                    "time",
                    start_date=self.start_date,
                    end_date=self.end_date,
                    timezone=self.timezone,
                )
                if hasattr(time_strategy, "get_bucket_info"):
                    response["time_bucket_info"] = time_strategy.get_bucket_info()
            except Exception as e:
                log.warning(
                    "time_bucket_info_failed", error=str(e), error_type=type(e).__name__
                )
                # Continue without bucket info if there's an error

        # Add aggregation results for each dimension
        for dimension, results in aggregation_results.items():
            for metric in self.metrics:
                # Map API metric names to result keys
                result_key = "total_clicks" if metric == "clicks" else metric
                metric_key = f"{metric}_by_{dimension}"

                response["metrics"][metric_key] = []
                for result in results:
                    # Handle different field names from different strategies
                    if dimension == "time":
                        dimension_value = result.get("date", "unknown")
                    elif dimension == "short_code":
                        dimension_value = result.get(
                            "short_code", result.get("alias", "unknown")
                        )
                    else:
                        dimension_value = result.get(dimension, "unknown")

                    response["metrics"][metric_key].append(
                        {
                            dimension: dimension_value,
                            metric: result.get(result_key, 0),
                        }
                    )

        return response

    def build(self) -> tuple[Response, int]:
        if self.error is not None:
            return self.error

        import time

        start_time = time.time()

        try:
            # Build query
            query = self._build_click_query()
            if self.error is not None:
                return self.error
            if not query and self.scope == "anon":
                return self._fail({"error": "invalid short_code"}, 400)

            # Execute ALL stats in a SINGLE MongoDB call using $facet
            # This is critical for serverless (Vercel) - reduces latency from N*RTT to 1*RTT
            summary, aggregation_results = self._execute_all_stats(query)

            # Format response
            response = self._format_results(aggregation_results)
            response["summary"] = summary

            # Enhance response with metadata and computed metrics
            enhanced_response = format_stats_response_with_metadata(response)

            # Sample logging (20%)
            if should_sample("stats_query"):
                duration_ms = int((time.time() - start_time) * 1000)
                log.info(
                    "stats_query",
                    scope=self.scope,
                    short_code=self.short_code if self.scope == "anon" else None,
                    group_by=self.group_by,
                    metrics=self.metrics,
                    start_date=self.start_date.isoformat() if self.start_date else None,
                    end_date=self.end_date.isoformat() if self.end_date else None,
                    filter_count=len(self.filters),
                    total_clicks=summary.get("total_clicks", 0),
                    unique_clicks=summary.get("unique_clicks", 0),
                    duration_ms=duration_ms,
                    slow_query=duration_ms > 5000,
                )

            return jsonify(enhanced_response), 200

        except Exception as e:
            log.error(
                "stats_query_failed",
                scope=self.scope,
                error=str(e),
                error_type=type(e).__name__,
            )
            return jsonify({"error": "database error"}), 500
