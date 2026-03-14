"""
Repository for the `urls` collection (v1 legacy schema).

Key differences from the v2 UrlRepository:
- _id IS the short code string (not an ObjectId).
- Field names use hyphens: "max-clicks", "total-clicks", etc.
- Passwords are stored in plaintext (backward compatibility).
- Analytics are embedded on the URL document (not in a separate collection).
- The update_one() method receives a pre-built MongoDB update document
  (with $inc/$set/$addToSet operators) from the service layer — the
  repository does NOT build the update document itself. This preserves
  the exact embedded analytics update patterns from the legacy code.

All methods are async. Errors are logged and re-raised.
"""

from __future__ import annotations

from typing import Any, Optional

from pymongo.asynchronous.collection import AsyncCollection

from schemas.models.url import LegacyUrlDoc
from shared.logging import get_logger

log = get_logger(__name__)


class LegacyUrlRepository:
    def __init__(self, collection: AsyncCollection) -> None:
        self._col = collection

    async def find_by_id(self, short_code: str) -> Optional[LegacyUrlDoc]:
        """Find a v1 URL document by its short code (_id)."""
        try:
            doc = await self._col.find_one({"_id": short_code})
            return LegacyUrlDoc.from_mongo(doc)  # type: ignore[return-value]
        except Exception as exc:
            log.error(
                "legacy_url_repo_find_failed",
                short_code=short_code,
                error=str(exc),
            )
            raise

    async def insert(self, short_code: str, url_data: dict) -> None:
        """
        Insert a new v1 URL document with the short code as _id.

        The caller must not include ``_id`` in url_data — it is set here.
        """
        try:
            await self._col.insert_one({"_id": short_code, **url_data})
        except Exception as exc:
            log.error(
                "legacy_url_repo_insert_failed",
                short_code=short_code,
                error=str(exc),
            )
            raise

    async def update(self, short_code: str, update_ops: dict) -> None:
        """
        Apply a pre-built MongoDB update document to a v1 URL.

        The update document is built by the click service using the exact
        $inc/$set/$addToSet pattern from the legacy handle_legacy_click().
        The repository does not interpret or construct the update — it
        executes it as-is to preserve the exact embedded analytics format.
        """
        try:
            await self._col.update_one({"_id": short_code}, update_ops)
        except Exception as exc:
            log.error(
                "legacy_url_repo_update_failed",
                short_code=short_code,
                error=str(exc),
            )
            raise

    async def check_exists(self, short_code: str) -> bool:
        """Return True if the short code exists in the collection."""
        try:
            doc = await self._col.find_one({"_id": short_code}, {"_id": 1})
            return doc is not None
        except Exception as exc:
            log.error(
                "legacy_url_repo_check_exists_failed",
                short_code=short_code,
                error=str(exc),
            )
            raise

    async def aggregate(self, pipeline: list[dict]) -> Optional[dict[str, Any]]:
        """
        Run an aggregation pipeline and return the first result document.

        Returns None if the pipeline produces no results (mirrors the legacy
        aggregate_url() behaviour).
        """
        try:
            cursor = await self._col.aggregate(pipeline)
            results = await cursor.to_list(length=1)
            return results[0] if results else None
        except Exception as exc:
            log.error("legacy_url_repo_aggregate_failed", error=str(exc))
            raise
