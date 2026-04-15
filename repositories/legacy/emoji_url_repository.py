"""
Repository for the `emojis` MongoDB collection.

Identical structure to LegacyUrlRepository — same schema (EmojiUrlDoc
extends LegacyUrlDoc), same v1 update patterns. The only difference is
which MongoDB collection operations target.
"""

from __future__ import annotations

from typing import Any

from pymongo.errors import DuplicateKeyError, PyMongoError, WriteError

from infrastructure.logging import get_logger
from repositories.base import BaseRepository
from schemas.models.url import EmojiUrlDoc

log = get_logger(__name__)

_DOCUMENT_TOO_LARGE_CODE = 10334


class EmojiUrlRepository(BaseRepository[EmojiUrlDoc]):
    async def find_by_id(self, alias: str) -> EmojiUrlDoc | None:
        """Find an emoji URL document by its alias (_id)."""
        return await self._find_one({"_id": alias})

    async def insert(self, alias: str, url_data: dict) -> None:
        """Insert a new emoji URL document with the alias as _id.

        The caller must not include ``_id`` in url_data — it is set here.
        """
        try:
            await self._col.insert_one({**url_data, "_id": alias})
        except DuplicateKeyError as exc:
            log.warning(
                "repo_insert_duplicate",
                collection=self._collection_name,
                alias=alias,
                error=str(exc),
            )
            raise
        except PyMongoError as exc:
            log.error(
                "repo_insert_failed",
                collection=self._collection_name,
                alias=alias,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def update(self, alias: str, update_ops: dict) -> None:
        """Apply a pre-built MongoDB update document to an emoji URL.

        If the update exceeds MongoDB's 16 MB document limit (due to
        unbounded $addToSet IP arrays), only total-clicks is incremented.
        """
        try:
            await self._col.update_one({"_id": alias}, update_ops)
        except WriteError as exc:
            if exc.code != _DOCUMENT_TOO_LARGE_CODE:
                raise
            inc = update_ops.get("$inc", {}).get("total-clicks", 1)
            try:
                await self._col.update_one(
                    {"_id": alias}, {"$inc": {"total-clicks": inc}}
                )
            except PyMongoError as retry_exc:
                log.error(
                    "repo_overflow_retry_failed",
                    collection=self._collection_name,
                    alias=alias,
                    error=str(retry_exc),
                    error_type=type(retry_exc).__name__,
                )
                raise
            log.info(
                "repo_document_overflow",
                collection=self._collection_name,
                alias=alias,
                msg="document exceeded 16 MB limit; click recorded with total-clicks only",
            )
        except PyMongoError as exc:
            log.error(
                "repo_update_failed",
                collection=self._collection_name,
                alias=alias,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def check_exists(self, alias: str) -> bool:
        """Return True if the emoji alias exists in the collection."""
        doc = await self._find_one_raw({"_id": alias}, {"_id": 1})
        return doc is not None

    async def aggregate(self, pipeline: list[dict]) -> dict[str, Any] | None:
        """Run an aggregation pipeline and return the first result document.

        Returns None if the pipeline produces no results.
        """
        results = await self._aggregate(pipeline)
        return results[0] if results else None
