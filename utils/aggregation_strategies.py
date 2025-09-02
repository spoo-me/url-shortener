from abc import ABC, abstractmethod
from typing import List, Dict, Any
from utils.analytics_utils import convert_country_name


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
    """Strategy for time-based aggregation"""

    def __init__(self, time_format: str = "%Y-%m-%d"):
        self.time_format = time_format

    def build_pipeline(self, base_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"$match": base_query},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": self.time_format,
                            "date": "$clicked_at",
                        }
                    },
                    "total_clicks": {"$sum": 1},
                    "unique_clicks": {"$addToSet": "$ip_address"},
                }
            },
            {"$addFields": {"unique_clicks": {"$size": "$unique_clicks"}}},
            {"$sort": {"_id": 1}},
        ]

    def format_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "date": result["_id"],
                "total_clicks": result.get("total_clicks", 0),
                "unique_clicks": result.get("unique_clicks", 0),
            }
            for result in results
        ]

    @property
    def dimension_name(self) -> str:
        return "time"


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


class KeyAggregationStrategy(AggregationStrategy):
    """Strategy for key-based aggregation (grouping by short codes/aliases)"""

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
        return "key"


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
        "key": KeyAggregationStrategy,
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
