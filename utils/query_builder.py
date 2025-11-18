from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId

from utils.logger import get_logger

log = get_logger(__name__)


class StatsQueryBuilder:
    """Builder pattern for constructing MongoDB queries for statistics"""

    def __init__(self):
        self.query: Dict[str, Any] = {}
        self.time_filters: Dict[str, datetime] = {}
        self.scope_filters: Dict[str, Any] = {}
        self.dimension_filters: Dict[str, List[str]] = {}

    def with_scope(
        self,
        owner_id: Optional[str],
        scope: str,
        short_code: Optional[str] = None,
    ) -> "StatsQueryBuilder":
        """Add scope-based filtering to the query"""
        if scope == "all" and owner_id:
            self.scope_filters["meta.owner_id"] = (
                ObjectId(owner_id) if isinstance(owner_id, str) else owner_id
            )
        elif scope == "anon" and short_code:
            self.scope_filters["meta.short_code"] = short_code

        return self

    def with_time_range(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> "StatsQueryBuilder":
        """Add time range filtering to the query"""
        if start_date:
            self.time_filters["$gte"] = start_date
        if end_date:
            self.time_filters["$lte"] = end_date

        return self

    def with_filters(self, filters: Dict[str, List[str]]) -> "StatsQueryBuilder":
        """Add dimension-based filtering to the query"""
        for dimension, values in filters.items():
            if values:
                self.dimension_filters[dimension] = values

        return self

    def build(self) -> Dict[str, Any]:
        """Build the final MongoDB query"""
        # Start with scope filters
        self.query.update(self.scope_filters)

        # Add time range filters
        if self.time_filters:
            self.query["clicked_at"] = self.time_filters

        # Add dimension filters
        for dimension, values in self.dimension_filters.items():
            if dimension == "short_code":
                # SECURITY: Only apply short_code filter if not already set by scope
                # This prevents filter-based scope bypass attacks
                if "meta.short_code" in self.scope_filters:
                    # Skip - short_code already locked by scope (anon mode)
                    log.warning(
                        "query_builder_scope_bypass_prevented",
                        dimension="short_code",
                        locked_short_code=self.scope_filters.get("meta.short_code"),
                        attempted_values=values,
                    )
                    continue
                # Map "short_code" filter to the actual field name in MongoDB
                self.query["meta.short_code"] = {"$in": values}
            elif dimension == "referrer":
                # Handle special case for "Direct" referrers (null/missing referrer)
                if "Direct" in values:
                    # Split Direct and non-Direct referrers
                    non_direct_values = [v for v in values if v != "Direct"]

                    if non_direct_values:
                        # Both Direct and specific referrers requested
                        self.query["$or"] = [
                            {"referrer": {"$in": non_direct_values}},
                            {"referrer": {"$in": [None, ""]}},
                            {"referrer": {"$exists": False}},
                        ]
                    else:
                        # Only Direct referrers requested
                        self.query["$or"] = [
                            {"referrer": {"$in": [None, ""]}},
                            {"referrer": {"$exists": False}},
                        ]
                else:
                    # No Direct referrers, normal filtering
                    self.query[dimension] = {"$in": values}
            else:
                self.query[dimension] = {"$in": values}

        return self.query


class StatsQueryBuilderFactory:
    """Factory for creating pre-configured query builders"""

    @staticmethod
    def for_user_stats(
        owner_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> StatsQueryBuilder:
        """Create a query builder for all user statistics"""
        return (
            StatsQueryBuilder()
            .with_scope(owner_id, "all")
            .with_time_range(start_date, end_date)
        )

    @staticmethod
    def for_anonymous_stats(
        short_code: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> StatsQueryBuilder:
        """Create a query builder for anonymous URL statistics"""
        return (
            StatsQueryBuilder()
            .with_scope(None, "anon", short_code=short_code)
            .with_time_range(start_date, end_date)
        )
