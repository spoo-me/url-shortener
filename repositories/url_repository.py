"""
Repository for the `urlsV2` MongoDB collection.

All methods are async and return typed Pydantic document models.
Errors are logged and re-raised — the service layer decides recovery.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection

from schemas.models.url import UrlV2Doc
from shared.logging import get_logger

log = get_logger(__name__)


class UrlRepository:
    def __init__(self, collection: AsyncCollection) -> None:
        self._col = collection

    async def find_by_alias(self, alias: str) -> Optional[UrlV2Doc]:
        """Find a URL document by its short alias."""
        try:
            doc = await self._col.find_one({"alias": alias})
            return UrlV2Doc.from_mongo(doc)  # type: ignore[return-value]
        except Exception as exc:
            log.error("url_repo_find_by_alias_failed", alias=alias, error=str(exc))
            raise

    async def find_by_id(self, url_id: ObjectId) -> Optional[UrlV2Doc]:
        """Find a URL document by its ObjectId."""
        try:
            doc = await self._col.find_one({"_id": url_id})
            return UrlV2Doc.from_mongo(doc)  # type: ignore[return-value]
        except Exception as exc:
            log.error("url_repo_find_by_id_failed", url_id=str(url_id), error=str(exc))
            raise

    async def insert(self, doc: dict) -> ObjectId:
        """Insert a new URL document. Returns the inserted _id."""
        try:
            result = await self._col.insert_one(doc)
            return result.inserted_id
        except Exception as exc:
            log.error(
                "url_repo_insert_failed",
                alias=doc.get("alias"),
                error=str(exc),
            )
            raise

    async def update(self, url_id: ObjectId, update_ops: dict) -> bool:
        """
        Apply a MongoDB update document (e.g. ``{"$set": {...}}``) to a URL.

        Returns True if the document was matched (and potentially modified).
        """
        try:
            result = await self._col.update_one({"_id": url_id}, update_ops)
            return result.matched_count > 0
        except Exception as exc:
            log.error("url_repo_update_failed", url_id=str(url_id), error=str(exc))
            raise

    async def delete(self, url_id: ObjectId) -> bool:
        """Hard-delete a URL document. Returns True if a document was deleted."""
        try:
            result = await self._col.delete_one({"_id": url_id})
            return result.deleted_count > 0
        except Exception as exc:
            log.error("url_repo_delete_failed", url_id=str(url_id), error=str(exc))
            raise

    async def check_alias_exists(self, alias: str) -> bool:
        """Return True if the alias already exists in the collection."""
        try:
            doc = await self._col.find_one({"alias": alias}, {"_id": 1})
            return doc is not None
        except Exception as exc:
            log.error("url_repo_check_alias_failed", alias=alias, error=str(exc))
            raise

    async def increment_clicks(
        self,
        url_id: ObjectId,
        last_click_time: Optional[datetime] = None,
        increment: int = 1,
    ) -> None:
        """Atomically increment total_clicks and update last_click timestamp."""
        click_time = last_click_time or datetime.now(timezone.utc)
        try:
            await self._col.update_one(
                {"_id": url_id},
                {
                    "$inc": {"total_clicks": increment},
                    "$set": {"last_click": click_time},
                },
            )
        except Exception as exc:
            log.error(
                "url_repo_increment_clicks_failed",
                url_id=str(url_id),
                error=str(exc),
            )
            raise

    async def expire_if_max_clicks(self, url_id: ObjectId, max_clicks: int) -> bool:
        """
        Conditionally expire the URL if total_clicks >= max_clicks.

        This is an atomic conditional update — not a read-then-write.
        Returns True if the URL was expired (document was modified).
        """
        try:
            result = await self._col.update_one(
                {"_id": url_id, "total_clicks": {"$gte": max_clicks}},
                {"$set": {"status": "EXPIRED"}},
            )
            return result.modified_count > 0
        except Exception as exc:
            log.error(
                "url_repo_expire_failed",
                url_id=str(url_id),
                max_clicks=max_clicks,
                error=str(exc),
            )
            raise

    async def find_by_owner(
        self,
        query: dict,
        sort_field: str,
        sort_order: int,
        skip: int,
        limit: int,
    ) -> list[UrlV2Doc]:
        """
        Return a page of UrlV2Doc models matching `query`.

        The query must already include the owner_id filter (built by the
        service layer). Returns typed models — serialisation to response
        shape is the service/route's responsibility.
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
        except Exception as exc:
            log.error("url_repo_find_by_owner_failed", error=str(exc))
            raise

    async def count_by_query(self, query: dict) -> int:
        """Count documents matching query."""
        try:
            return await self._col.count_documents(query)
        except Exception as exc:
            log.error("url_repo_count_failed", error=str(exc))
            raise
