"""
Repository for the `urls` collection (v1 legacy schema).

Key differences from the v2 UrlRepository:
- _id IS the short code string (not an ObjectId).
- Field names use hyphens: "max-clicks", "total-clicks", etc.
- Passwords are stored in plaintext (backward compatibility).
- Analytics are embedded on the URL document (not in a separate collection).
- The update() method has overflow-retry logic for the 16 MB document limit.
"""

from __future__ import annotations

from typing import Any

from pymongo.errors import DuplicateKeyError, PyMongoError, WriteError

from infrastructure.logging import get_logger
from repositories.base import BaseRepository
from schemas.models.url import LegacyUrlDoc

log = get_logger(__name__)

_DOCUMENT_TOO_LARGE_CODE = 10334


class LegacyUrlRepository(BaseRepository[LegacyUrlDoc]):
    async def find_by_id(self, short_code: str) -> LegacyUrlDoc | None:
        """Find a v1 URL document by its short code (_id)."""
        return await self._find_one({"_id": short_code})

    async def insert(self, short_code: str, url_data: dict) -> None:
        """Insert a new v1 URL document with the short code as _id.

        The caller must not include ``_id`` in url_data — it is set here.
        """
        try:
            await self._col.insert_one({**url_data, "_id": short_code})
        except DuplicateKeyError as exc:
            log.warning(
                "repo_insert_duplicate",
                collection=self._collection_name,
                short_code=short_code,
                error=str(exc),
            )
            raise
        except PyMongoError as exc:
            log.error(
                "repo_insert_failed",
                collection=self._collection_name,
                short_code=short_code,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def update(self, short_code: str, update_ops: dict) -> None:
        """Apply a pre-built MongoDB update document to a v1 URL.

        If the update exceeds MongoDB's 16 MB document limit (due to
        unbounded $addToSet IP arrays), only total-clicks is incremented.
        """
        try:
            await self._col.update_one({"_id": short_code}, update_ops)
        except WriteError as exc:
            if exc.code != _DOCUMENT_TOO_LARGE_CODE:
                raise
            # $inc on an existing integer never changes BSON size.
            inc = update_ops.get("$inc", {}).get("total-clicks", 1)
            try:
                await self._col.update_one(
                    {"_id": short_code}, {"$inc": {"total-clicks": inc}}
                )
            except PyMongoError as retry_exc:
                log.error(
                    "repo_overflow_retry_failed",
                    collection=self._collection_name,
                    short_code=short_code,
                    error=str(retry_exc),
                    error_type=type(retry_exc).__name__,
                )
                raise
            log.info(
                "repo_document_overflow",
                collection=self._collection_name,
                short_code=short_code,
                msg="document exceeded 16 MB limit; click recorded with total-clicks only",
            )
        except PyMongoError as exc:
            log.error(
                "repo_update_failed",
                collection=self._collection_name,
                short_code=short_code,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def check_exists(self, short_code: str) -> bool:
        """Return True if the short code exists in the collection."""
        doc = await self._find_one_raw({"_id": short_code}, {"_id": 1})
        return doc is not None

    async def aggregate(self, pipeline: list[dict]) -> dict[str, Any] | None:
        """Run an aggregation pipeline and return the first result document.

        Returns None if the pipeline produces no results.
        """
        results = await self._aggregate(pipeline)
        return results[0] if results else None
