"""
Repository for the `urlsV2` MongoDB collection.

All methods are async and return typed Pydantic document models.
Errors are handled by BaseRepository — domain methods delegate to
shared CRUD helpers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

from bson import ObjectId
from pymongo.errors import PyMongoError

from repositories.base import BaseRepository
from schemas.models.url import UrlStatus, UrlV2Doc
from shared.logging import get_logger

log = get_logger(__name__)


class StatsPrivacyInfo(TypedDict):
    """Return type for check_stats_privacy."""

    exists: bool
    private: bool
    owner_id: str | None


class UrlRepository(BaseRepository[UrlV2Doc]):
    async def find_by_alias(self, alias: str) -> UrlV2Doc | None:
        """Find a URL document by its short alias."""
        return await self._find_one({"alias": alias})

    async def find_by_id(self, url_id: ObjectId) -> UrlV2Doc | None:
        """Find a URL document by its ObjectId."""
        return await self._find_one({"_id": url_id})

    async def insert(self, doc: dict) -> ObjectId:
        """Insert a new URL document. Returns the inserted _id."""
        return await self._insert(doc)

    async def update(self, url_id: ObjectId, update_ops: dict) -> bool:
        """Apply a MongoDB update document to a URL.

        Returns True if the document was matched (and potentially modified).
        """
        return await self._update({"_id": url_id}, update_ops)

    async def delete(self, url_id: ObjectId) -> bool:
        """Hard-delete a URL document. Returns True if a document was deleted."""
        return await self._delete({"_id": url_id})

    async def check_alias_exists(self, alias: str) -> bool:
        """Return True if the alias already exists in the collection."""
        doc = await self._find_one_raw({"alias": alias}, {"_id": 1})
        return doc is not None

    async def increment_clicks(
        self,
        url_id: ObjectId,
        last_click_time: datetime | None = None,
        increment: int = 1,
    ) -> None:
        """Atomically increment total_clicks and update last_click timestamp."""
        click_time = last_click_time or datetime.now(timezone.utc)
        await self._update(
            {"_id": url_id},
            {
                "$inc": {"total_clicks": increment},
                "$set": {"last_click": click_time},
            },
        )

    async def expire_if_max_clicks(self, url_id: ObjectId, max_clicks: int) -> bool:
        """Conditionally expire the URL if total_clicks >= max_clicks.

        This is an atomic conditional update — not a read-then-write.
        Returns True if the URL was expired (document was modified).
        """
        return await self._update(
            {"_id": url_id, "total_clicks": {"$gte": max_clicks}},
            {"$set": {"status": UrlStatus.EXPIRED}},
        )

    async def find_by_owner(
        self,
        query: dict,
        sort_field: str,
        sort_order: int,
        skip: int,
        limit: int,
    ) -> list[UrlV2Doc]:
        """Return a page of UrlV2Doc models matching *query*.

        The query must already include the owner_id filter (built by the
        service layer).
        """
        try:
            cursor = (
                self._col.find(query)
                .sort(sort_field, sort_order)
                .skip(skip)
                .limit(limit)
            )
            docs = await cursor.to_list(length=limit)
            return [UrlV2Doc.from_mongo(d) for d in docs]  # type: ignore[misc]
        except PyMongoError as exc:
            log.error(
                "repo_find_by_owner_failed",
                collection=self._collection_name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def count_by_query(self, query: dict) -> int:
        """Count documents matching query."""
        return await self._count(query)

    async def check_stats_privacy(self, alias: str) -> StatsPrivacyInfo:
        """Return privacy metadata for a URL alias."""
        doc = await self._find_one_raw(
            {"alias": alias}, {"private_stats": 1, "owner_id": 1}
        )
        if not doc:
            return {"exists": False, "private": False, "owner_id": None}
        return {
            "exists": True,
            "private": bool(doc.get("private_stats", False)),
            "owner_id": str(doc["owner_id"]) if doc.get("owner_id") else None,
        }
