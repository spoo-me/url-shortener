from flask import request, jsonify, Response
from datetime import datetime, timezone, timedelta
import json
from typing import Optional, Any, List, Dict
from zoneinfo import ZoneInfo, available_timezones

from utils.mongo_utils import (
    clicks_collection,
    validate_url_ownership,
    check_url_stats_privacy,
)
from utils.aggregation_strategies import AggregationStrategyFactory
from utils.query_builder import StatsQueryBuilderFactory
from utils.stats_utils import format_stats_response_with_metadata, validate_date_range


class StatsQueryBuilder:
    """Builder for querying URL statistics with filtering, grouping, and aggregation"""

    def __init__(self, owner_id, args: dict[str, Any]):
        self.owner_id = owner_id
        self.args = args
        self.error: Optional[tuple[Response, int]] = None

        # Query parameters
        self.scope: str = "all"  # "all" | "url" | "anon"
        self.url_id: Optional[str] = None
        self.short_code: Optional[str] = None
        self.start_date: Optional[datetime] = None
        self.end_date: Optional[datetime] = None
        self.filters: Dict[str, List[str]] = {}
        self.group_by: List[str] = []
        self.metrics: List[str] = ["clicks", "unique_clicks"]
        self.timezone: str = "UTC"  # IANA timezone for output formatting

        # Allowed values
        self.allowed_scopes = {"all", "url", "anon"}
        self.allowed_group_by = {
            "time",
            "browser",
            "os",
            # "device",  # DISABLED: Reliable device detection not available yet
            "country",
            "city",
            "referrer",
            "key",
        }
        self.allowed_metrics = {"clicks", "unique_clicks"}
        # Allowed dimensions for filtering statistics
        # TODO: "device" is disabled until reliable device detection is implemented
        self.allowed_filters = {"browser", "os", "country", "city", "referrer", "key"}

    def _fail(self, body: dict, status: int) -> "StatsQueryBuilder":
        self.error = (jsonify(body), status)
        return self

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(int(value), tz=timezone.utc)
            dt = datetime.fromisoformat(str(value))
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
            print(f"Timezone conversion error: {e}")
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

        if self.scope == "url":
            self.url_id = self.args.get("url_id", "").strip()
            if not self.url_id:
                return self._fail({"error": "url_id is required when scope=url"}, 400)
            if self.owner_id is None:
                return self._fail(
                    {"error": "authentication required for scope=url"}, 401
                )

            # Validate URL ownership - ensure the URL belongs to the authenticated user
            if not validate_url_ownership(self.url_id, self.owner_id):
                return self._fail({"error": "url not found or access denied"}, 404)

        elif self.scope == "anon":
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
                    return self._fail(
                        {
                            "error": "this URL has private statistics - authentication required"
                        },
                        401,
                    )

                # Check if authenticated user owns this URL
                if privacy_info["owner_id"] != str(self.owner_id):
                    return self._fail(
                        {"error": "access denied - private statistics"}, 403
                    )

        elif self.scope == "all":
            if self.owner_id is None:
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
                self.filters[filter_name] = self._parse_comma_separated(filter_value)

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
            print(f"Invalid timezone '{timezone_raw}' provided, falling back to UTC")
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
            elif self.scope == "url":
                builder = StatsQueryBuilderFactory.for_url_stats(
                    str(self.owner_id), self.url_id, self.start_date, self.end_date
                )
            elif self.scope == "anon":
                builder = StatsQueryBuilderFactory.for_anonymous_stats(
                    self.short_code, self.start_date, self.end_date
                )
            else:
                return {}

            # Add dimension filters
            builder.with_filters(self.filters)

            return builder.build()

        except Exception as e:
            print(f"Error building query: {e}")
            return {}

    def _build_aggregation_pipeline(
        self, query: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build aggregation pipeline for statistics using strategy pattern"""
        # For multiple group_by dimensions, we'll need to run separate aggregations
        # and combine the results in _execute_aggregations
        return []  # This will be handled by strategy pattern

    def _execute_aggregations(
        self, query: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Execute aggregations for each group_by dimension using strategies"""
        results = {}

        for group_dimension in self.group_by:
            try:
                # Pass time range information for time aggregation strategy
                if group_dimension == "time":
                    strategy = AggregationStrategyFactory.get(
                        group_dimension,
                        start_date=self.start_date,
                        end_date=self.end_date,
                        timezone=self.timezone,  # Pass timezone for output conversion
                    )
                else:
                    strategy = AggregationStrategyFactory.get(group_dimension)

                pipeline = strategy.build_pipeline(query)
                raw_results = list(clicks_collection.aggregate(pipeline))
                formatted_results = strategy.format_results(raw_results)
                results[group_dimension] = formatted_results
            except Exception as e:
                print(f"Error executing {group_dimension} aggregation: {e}")
                results[group_dimension] = []

        return results

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
        if self.scope == "url":
            response["url_id"] = self.url_id
        elif self.scope == "anon":
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
                print(f"Error getting bucket info: {e}")
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
                    elif dimension == "key":
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

    def _get_summary_stats(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Get overall summary statistics"""
        pipeline = [
            {"$match": query},
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

        try:
            result = list(clicks_collection.aggregate(pipeline))
            if result:
                summary = result[0]
                return {
                    "total_clicks": summary.get("total_clicks", 0),
                    "unique_clicks": summary.get("unique_clicks", 0),
                    "first_click": self._format_datetime_in_timezone(
                        summary.get("first_click")
                    ),
                    "last_click": self._format_datetime_in_timezone(
                        summary.get("last_click")
                    ),
                    "avg_redirection_time": round(
                        summary.get("avg_redirection_time", 0), 2
                    ),
                }
        except Exception:
            pass

        return {
            "total_clicks": 0,
            "unique_clicks": 0,
            "first_click": None,
            "last_click": None,
            "avg_redirection_time": 0,
        }

    def build(self) -> tuple[Response, int]:
        if self.error is not None:
            return self.error

        try:
            # Build query
            query = self._build_click_query()
            if not query and self.scope in ["url", "anon"]:
                return self._fail({"error": "invalid url_id or short_code"}, 400)

            # Get summary statistics
            summary = self._get_summary_stats(query)

            # Execute aggregations using strategy pattern
            aggregation_results = self._execute_aggregations(query)

            # Format response
            response = self._format_results(aggregation_results)
            response["summary"] = summary

            # Enhance response with metadata and computed metrics
            enhanced_response = format_stats_response_with_metadata(response)

            return jsonify(enhanced_response), 200

        except Exception as e:
            print(f"Stats query error: {e}")
            return jsonify({"error": "database error"}), 500
