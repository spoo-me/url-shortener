from flask import request, jsonify, Response
from datetime import datetime, timezone
import json
import re
from typing import Optional, Any

from utils.mongo_utils import urls_v2_collection


class UrlListQueryBuilder:
    """Builder for querying and listing URLs with pagination, filtering, and sorting"""

    def __init__(self, owner_id, args: dict[str, Any]):
        self.owner_id = owner_id
        self.args = args
        self.error: Optional[tuple[Response, int]] = None
        self.page: int = 1
        self.page_size: int = 20
        self.sort_field: str = "created_at"
        self.sort_order: int = -1  # -1 desc, 1 asc
        self.filters: dict[str, Any] = {}
        self.query: dict[str, Any] = {"owner_id": owner_id}
        self.allowed_sort_fields = {"created_at", "last_click", "total_clicks"}
        self.projection = {
            "_id": 1,
            "alias": 1,
            "long_url": 1,
            "status": 1,
            "created_at": 1,
            "expire_after": 1,
            "max_clicks": 1,
            "private_stats": 1,
            "password": 1,
            "total_clicks": 1,
            "last_click": 1,
        }

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

    def _parse_bool(self, value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in ("true", "1", "yes"):  # common truthy
            return True
        if s in ("false", "0", "no"):  # common falsy
            return False
        return None

    def _fail(self, body: dict, status: int) -> "UrlListQueryBuilder":
        self.error = (jsonify(body), status)
        return self

    def parse_auth_scope(self) -> "UrlListQueryBuilder":
        api_key_doc = getattr(request, "api_key", None)
        if api_key_doc is not None:
            scopes = set(api_key_doc.get("scopes", []))
            if (
                "admin:all" not in scopes
                and "urls:manage" not in scopes
                and "urls:read" not in scopes
            ):
                return self._fail(
                    {"error": "api key lacks required scope: urls:manage"}, 403
                )
        return self

    def parse_pagination(self) -> "UrlListQueryBuilder":
        try:
            self.page = int(self.args.get("page", 1))
            self.page_size = int(self.args.get("pageSize", 20))
        except Exception:
            return self._fail({"error": "page and pageSize must be integers"}, 400)
        if self.page < 1:
            return self._fail({"error": "page must be >= 1", "field": "page"}, 400)
        if self.page_size < 1 or self.page_size > 100:
            return self._fail(
                {"error": "pageSize must be between 1 and 100", "field": "pageSize"},
                400,
            )
        return self

    def parse_sort(self) -> "UrlListQueryBuilder":
        sort_by = (self.args.get("sortBy") or "created_at").strip()
        sort_order_raw = (self.args.get("sortOrder") or "descending").strip().lower()
        self.sort_order = -1 if sort_order_raw in ("desc", "descending", "-1") else 1
        self.sort_field = (
            sort_by if sort_by in self.allowed_sort_fields else "created_at"
        )
        return self

    def parse_filters(self) -> "UrlListQueryBuilder":
        filter_raw = self.args.get("filter") or self.args.get("filterBy")
        if filter_raw:
            try:
                self.filters = json.loads(filter_raw)
                if not isinstance(self.filters, dict):
                    return self._fail(
                        {"error": "filter must be a JSON object", "field": "filter"},
                        400,
                    )
            except json.JSONDecodeError:
                return self._fail(
                    {"error": "filter must be valid JSON", "field": "filter"}, 400
                )

        status_val = self.filters.get("status")
        if status_val:
            self.query["status"] = status_val

        created_after = (
            self._parse_datetime(self.filters.get("createdAfter"))
            if "createdAfter" in self.filters
            else None
        )
        created_before = (
            self._parse_datetime(self.filters.get("createdBefore"))
            if "createdBefore" in self.filters
            else None
        )
        if created_after or created_before:
            created_range: dict[str, Any] = {}
            if created_after:
                created_range["$gte"] = created_after
            if created_before:
                created_range["$lte"] = created_before
            self.query["created_at"] = created_range

        password_set = (
            self._parse_bool(self.filters.get("passwordSet"))
            if "passwordSet" in self.filters
            else None
        )
        if password_set is True:
            self.query["password"] = {"$ne": None}
        elif password_set is False:
            self.query["password"] = None

        max_clicks_set = (
            self._parse_bool(self.filters.get("maxClicksSet"))
            if "maxClicksSet" in self.filters
            else None
        )
        if max_clicks_set is True:
            self.query["max_clicks"] = {"$ne": None}
        elif max_clicks_set is False:
            self.query["max_clicks"] = None

        search_term = (
            (self.filters.get("search") or "").strip()
            if isinstance(self.filters.get("search"), str)
            else ""
        )
        if search_term:
            try:
                pattern = re.compile(re.escape(search_term), re.IGNORECASE)
                self.query["$or"] = [{"alias": pattern}, {"long_url": pattern}]
            except re.error:
                return self._fail(
                    {"error": "invalid search pattern", "field": "filter.search"},
                    400,
                )

        # Placeholder: clicks filters to be implemented later
        return self

    def build(self) -> tuple[Response, int]:
        if self.error is not None:
            return self.error

        skip = (self.page - 1) * self.page_size
        limit = self.page_size

        try:
            total = urls_v2_collection.count_documents(self.query)
            cursor = (
                urls_v2_collection.find(self.query, self.projection)
                .sort(self.sort_field, self.sort_order)
                .skip(skip)
                .limit(limit)
            )
            docs = list(cursor)
        except Exception:
            return jsonify({"error": "database error"}), 500

        items = []
        for d in docs:
            created_at_iso = (
                d["created_at"]
                .astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
                if d.get("created_at")
                else None
            )
            expire_after_ts = (
                int(d["expire_after"])
                if isinstance(d.get("expire_after"), (int, float))
                else None
            )
            password_present = d.get("password") is not None
            items.append(
                {
                    "id": str(d["_id"]),
                    "alias": d.get("alias"),
                    "long_url": d.get("long_url"),
                    "status": d.get("status"),
                    "created_at": created_at_iso,
                    "expire_after": expire_after_ts,
                    "max_clicks": d.get("max_clicks"),
                    "private_stats": d.get("private_stats"),
                    "password_set": password_present,
                    # Placeholders until implemented/populated
                    "total_clicks": d.get("total_clicks"),
                    "last_click": int(d["last_click"].timestamp())
                    if d.get("last_click")
                    else None,
                }
            )

        has_next = (skip + len(items)) < total
        body = {
            "items": items,
            "page": self.page,
            "pageSize": self.page_size,
            "total": total,
            "hasNext": has_next,
            "sortBy": self.sort_field,
            "sortOrder": "descending" if self.sort_order == -1 else "ascending",
        }
        return jsonify(body), 200
