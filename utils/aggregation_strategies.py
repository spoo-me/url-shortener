from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from utils.analytics_utils import convert_country_name
from utils.time_bucket_utils import (
    get_optimal_bucket_config,
    create_mongo_time_bucket_pipeline,
    format_time_bucket_display,
    fill_missing_buckets,
)

import logging

log = logging.getLogger(__name__)


class AggregationStrategy(ABC):
    """Abstract base class for aggregation strategies"""

    @abstractmethod
    def build_pipeline(self, base_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build aggregation pipeline for this strategy"""
        pass

    @abstractmethod
    def format_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format the aggregation results"""
        pass

    @property
    @abstractmethod
    def dimension_name(self) -> str:
        """Get the dimension name for this strategy"""
        pass


class TimeAggregationStrategy(AggregationStrategy):
    """Strategy for time-based aggregation with dynamic bucketing"""

    def __init__(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        time_format: Optional[str] = None,
        timezone: str = "UTC",
    ):
        """
        Initialize time aggregation strategy.

        Args:
            start_date: Start date for determining optimal bucket strategy
            end_date: End date for determining optimal bucket strategy
            time_format: Manual override for time format (legacy support)
            timezone: IANA timezone for output formatting (default: UTC)
        """
        self.start_date = start_date
        self.end_date = end_date
        self.timezone = timezone

        # Determine bucket configuration
        if time_format:
            # Legacy mode: use provided format
            self.bucket_config = None
            self.time_format = time_format
        else:
            # Dynamic mode: determine optimal bucketing
            self.bucket_config = get_optimal_bucket_config(start_date, end_date)
            self.time_format = self.bucket_config.mongo_format

    def build_pipeline(self, base_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build aggregation pipeline with dynamic time bucketing"""

        if self.bucket_config:
            # Use dynamic bucketing with specialized pipeline and timezone support
            time_bucket_expr = create_mongo_time_bucket_pipeline(
                self.bucket_config, timezone=self.timezone
            )
        else:
            # Legacy mode: use simple dateToString with timezone
            time_bucket_expr = {
                "$dateToString": {
                    "format": self.time_format,
                    "date": "$clicked_at",
                    "timezone": self.timezone,
                }
            }

        return [
            {"$match": base_query},
            {
                "$group": {
                    "_id": time_bucket_expr,
                    "total_clicks": {"$sum": 1},
                    "unique_clicks": {"$addToSet": "$ip_address"},
                }
            },
            {"$addFields": {"unique_clicks": {"$size": "$unique_clicks"}}},
            {"$sort": {"_id": 1}},
        ]

    def format_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format results with proper time bucket display and fill missing buckets"""
        formatted_results = []

        for result in results:
            bucket_value = result["_id"]

            # Format the time bucket for display if using dynamic bucketing
            # NOTE: Buckets are already in user's timezone from MongoDB aggregation
            if self.bucket_config:
                display_value = format_time_bucket_display(
                    bucket_value, self.bucket_config
                )
            else:
                display_value = bucket_value

            formatted_results.append(
                {
                    "date": display_value,
                    "total_clicks": result.get("total_clicks", 0),
                    "unique_clicks": result.get("unique_clicks", 0),
                    "bucket_strategy": self.bucket_config.strategy.value
                    if self.bucket_config
                    else "legacy",
                    "raw_bucket": bucket_value,  # Include raw value for debugging
                }
            )

        # Fill missing buckets if using dynamic bucketing and we have date range
        # NOTE: We need to convert start/end dates to user timezone for proper bucket filling
        if self.bucket_config and self.start_date and self.end_date:
            # Convert date range to user timezone for bucket generation
            from zoneinfo import ZoneInfo

            user_tz = ZoneInfo(self.timezone)
            start_in_tz = self.start_date.astimezone(user_tz)
            end_in_tz = self.end_date.astimezone(user_tz)

            formatted_results = fill_missing_buckets(
                formatted_results, start_in_tz, end_in_tz, self.bucket_config
            )

        return formatted_results

    def _convert_bucket_to_timezone(self, bucket_str: str) -> str:
        """Convert UTC bucket timestamp to user's timezone"""
        if self.timezone == "UTC":
            return bucket_str  # No conversion needed

        try:
            user_tz = ZoneInfo(self.timezone)

            # Parse the bucket string based on its format
            if self.bucket_config:
                strategy = self.bucket_config.strategy.value

                if "minute" in strategy or "hourly" in strategy:
                    # Format: "2025-01-01 14:30" or "2025-01-01 14:00"
                    dt = datetime.strptime(bucket_str, "%Y-%m-%d %H:%M")
                elif "daily" in strategy:
                    # Format: "2025-01-01"
                    dt = datetime.strptime(bucket_str, "%Y-%m-%d")
                elif "weekly" in strategy:
                    # Format: "2025-W01" - keep as is for now
                    return bucket_str
                elif "monthly" in strategy:
                    # Format: "2025-01"
                    dt = datetime.strptime(bucket_str, "%Y-%m")
                else:
                    return bucket_str
            else:
                # Legacy mode - try common formats
                try:
                    dt = datetime.strptime(bucket_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    try:
                        dt = datetime.strptime(bucket_str, "%Y-%m-%d")
                    except ValueError:
                        return bucket_str

            # Treat parsed datetime as UTC and convert to user timezone
            from datetime import timezone as dt_timezone

            dt_utc = dt.replace(tzinfo=dt_timezone.utc)
            dt_user = dt_utc.astimezone(user_tz)

            # Format back to string in the same format
            if self.bucket_config:
                strategy = self.bucket_config.strategy.value
                if "minute" in strategy or "hourly" in strategy:
                    return dt_user.strftime("%Y-%m-%d %H:%M")
                elif "daily" in strategy:
                    return dt_user.strftime("%Y-%m-%d")
                elif "monthly" in strategy:
                    return dt_user.strftime("%Y-%m")

            return dt_user.strftime("%Y-%m-%d %H:%M")

        except Exception as e:
            log.error(
                "time_bucket_timezone_conversion_failed",
                bucket=bucket_str,
                timezone=self.timezone,
                error=str(e),
                error_type=type(e).__name__,
            )
            return bucket_str  # Return original on error

    @property
    def dimension_name(self) -> str:
        return "time"

    def get_bucket_info(self) -> Dict[str, Any]:
        """Get information about the current bucketing strategy"""
        if self.bucket_config:
            return {
                "strategy": self.bucket_config.strategy.value,
                "interval_minutes": self.bucket_config.interval_minutes,
                "mongo_format": self.bucket_config.mongo_format,
                "display_format": self.bucket_config.display_format,
                "timezone": self.timezone,
            }
        else:
            return {
                "strategy": "legacy",
                "mongo_format": self.time_format,
                "display_format": self.time_format,
                "timezone": self.timezone,
            }


class BrowserAggregationStrategy(AggregationStrategy):
    """Strategy for browser-based aggregation"""

    def build_pipeline(self, base_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"$match": base_query},
            {
                "$group": {
                    "_id": {"$ifNull": ["$browser", "Unknown"]},
                    "total_clicks": {"$sum": 1},
                    "unique_clicks": {"$addToSet": "$ip_address"},
                }
            },
            {"$addFields": {"unique_clicks": {"$size": "$unique_clicks"}}},
            {"$sort": {"total_clicks": -1}},
        ]

    def format_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "browser": result["_id"],
                "total_clicks": result.get("total_clicks", 0),
                "unique_clicks": result.get("unique_clicks", 0),
            }
            for result in results
        ]

    @property
    def dimension_name(self) -> str:
        return "browser"


class OSAggregationStrategy(AggregationStrategy):
    """Strategy for operating system aggregation"""

    def build_pipeline(self, base_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"$match": base_query},
            {
                "$group": {
                    "_id": {"$ifNull": ["$os", "Unknown"]},
                    "total_clicks": {"$sum": 1},
                    "unique_clicks": {"$addToSet": "$ip_address"},
                }
            },
            {"$addFields": {"unique_clicks": {"$size": "$unique_clicks"}}},
            {"$sort": {"total_clicks": -1}},
        ]

    def format_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "os": result["_id"],
                "total_clicks": result.get("total_clicks", 0),
                "unique_clicks": result.get("unique_clicks", 0),
            }
            for result in results
        ]

    @property
    def dimension_name(self) -> str:
        return "os"


class DeviceAggregationStrategy(AggregationStrategy):
    """Strategy for device type aggregation"""

    def build_pipeline(self, base_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"$match": base_query},
            {
                "$group": {
                    "_id": {"$ifNull": ["$device", "Unknown"]},
                    "total_clicks": {"$sum": 1},
                    "unique_clicks": {"$addToSet": "$ip_address"},
                }
            },
            {"$addFields": {"unique_clicks": {"$size": "$unique_clicks"}}},
            {"$sort": {"total_clicks": -1}},
        ]

    def format_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "device": result["_id"],
                "total_clicks": result.get("total_clicks", 0),
                "unique_clicks": result.get("unique_clicks", 0),
            }
            for result in results
        ]

    @property
    def dimension_name(self) -> str:
        return "device"


class CountryAggregationStrategy(AggregationStrategy):
    """Strategy for country-based aggregation"""

    def build_pipeline(self, base_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"$match": base_query},
            {
                "$group": {
                    "_id": {"$ifNull": ["$country", "Unknown"]},
                    "total_clicks": {"$sum": 1},
                    "unique_clicks": {"$addToSet": "$ip_address"},
                }
            },
            {"$addFields": {"unique_clicks": {"$size": "$unique_clicks"}}},
            {"$sort": {"total_clicks": -1}},
        ]

    def format_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "country": convert_country_name(
                    result["_id"]
                ),  # Send country code after conversion
                "total_clicks": result.get("total_clicks", 0),
                "unique_clicks": result.get("unique_clicks", 0),
            }
            for result in results
        ]

    @property
    def dimension_name(self) -> str:
        return "country"


class CityAggregationStrategy(AggregationStrategy):
    """Strategy for city-based aggregation"""

    def build_pipeline(self, base_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"$match": base_query},
            {
                "$group": {
                    "_id": {"$ifNull": ["$city", "Unknown"]},
                    "total_clicks": {"$sum": 1},
                    "unique_clicks": {"$addToSet": "$ip_address"},
                }
            },
            {"$addFields": {"unique_clicks": {"$size": "$unique_clicks"}}},
            {"$sort": {"total_clicks": -1}},
        ]

    def format_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "city": result["_id"],
                "total_clicks": result.get("total_clicks", 0),
                "unique_clicks": result.get("unique_clicks", 0),
            }
            for result in results
        ]

    @property
    def dimension_name(self) -> str:
        return "city"


class ReferrerAggregationStrategy(AggregationStrategy):
    """Strategy for referrer-based aggregation"""

    def build_pipeline(self, base_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"$match": base_query},
            {
                "$group": {
                    "_id": {"$ifNull": ["$referrer", "Direct"]},
                    "total_clicks": {"$sum": 1},
                    "unique_clicks": {"$addToSet": "$ip_address"},
                }
            },
            {"$addFields": {"unique_clicks": {"$size": "$unique_clicks"}}},
            {"$sort": {"total_clicks": -1}},
        ]

    def format_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "referrer": result["_id"],
                "total_clicks": result.get("total_clicks", 0),
                "unique_clicks": result.get("unique_clicks", 0),
            }
            for result in results
        ]

    @property
    def dimension_name(self) -> str:
        return "referrer"


class ShortCodeAggregationStrategy(AggregationStrategy):
    """Strategy for short_code-based aggregation (grouping by short codes/aliases)"""

    def build_pipeline(self, base_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"$match": base_query},
            {
                "$group": {
                    "_id": {"$ifNull": ["$meta.short_code", "Unknown"]},
                    "total_clicks": {"$sum": 1},
                    "unique_clicks": {"$addToSet": "$ip_address"},
                }
            },
            {"$addFields": {"unique_clicks": {"$size": "$unique_clicks"}}},
            {"$sort": {"total_clicks": -1}},
        ]

    def format_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "short_code": result["_id"],
                "total_clicks": result.get("total_clicks", 0),
                "unique_clicks": result.get("unique_clicks", 0),
            }
            for result in results
        ]

    @property
    def dimension_name(self) -> str:
        return "short_code"


class AggregationStrategyFactory:
    """Factory for creating aggregation strategies"""

    _strategies = {
        "time": TimeAggregationStrategy,
        "browser": BrowserAggregationStrategy,
        "os": OSAggregationStrategy,
        "device": DeviceAggregationStrategy,
        "country": CountryAggregationStrategy,
        "city": CityAggregationStrategy,
        "referrer": ReferrerAggregationStrategy,
        "short_code": ShortCodeAggregationStrategy,
    }

    @classmethod
    def get(cls, strategy_name: str, **kwargs) -> AggregationStrategy:
        """Get an aggregation strategy by name"""
        if strategy_name not in cls._strategies:
            raise ValueError(f"Unknown aggregation strategy: {strategy_name}")

        strategy_class = cls._strategies[strategy_name]
        return strategy_class(**kwargs)

    @classmethod
    def get_available_strategies(cls) -> List[str]:
        """Get list of available strategy names"""
        return list(cls._strategies.keys())
