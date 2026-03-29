"""
Repository for the `emojis` MongoDB collection.

Identical structure to LegacyUrlRepository — same schema (EmojiUrlDoc
extends LegacyUrlDoc), same v1 update patterns. The only difference is
which MongoDB collection operations target.

All methods are async. Errors are logged and re-raised.
"""

from __future__ import annotations

from typing import Any

from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError, PyMongoError, WriteError

from schemas.models.url import EmojiUrlDoc
from shared.logging import get_logger

log = get_logger(__name__)

_DOCUMENT_TOO_LARGE_CODE = 10334


class EmojiUrlRepository:
    def __init__(self, collection: AsyncCollection) -> None:
        self._col = collection

    async def find_by_id(self, alias: str) -> EmojiUrlDoc | None:
        """Find an emoji URL document by its alias (_id)."""
        try:
            doc = await self._col.find_one({"_id": alias})
            return EmojiUrlDoc.from_mongo(doc)
        except PyMongoError as exc:
            log.error(
                "emoji_url_repo_find_failed",
                alias=alias,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def insert(self, alias: str, url_data: dict) -> None:
        """
        Insert a new emoji URL document with the alias as _id.

        The caller must not include ``_id`` in url_data — it is set here.
        """
        try:
            await self._col.insert_one({"_id": alias, **url_data})
        except DuplicateKeyError as exc:
            log.warning("emoji_url_repo_insert_duplicate", alias=alias, error=str(exc))
            raise
        except PyMongoError as exc:
            log.error(
                "emoji_url_repo_insert_failed",
                alias=alias,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def update(self, alias: str, update_ops: dict) -> None:
        """
        Apply a pre-built MongoDB update document to an emoji URL.

        The update document is built by the click service using the exact
        $inc/$set/$addToSet pattern from the legacy handle_legacy_click().

        If the update exceeds MongoDB's 16 MB document limit (due to
        unbounded $addToSet IP arrays), only total-clicks is incremented.
        """
        try:
            await self._col.update_one({"_id": alias}, update_ops)
        except WriteError as exc:
            if exc.code != _DOCUMENT_TOO_LARGE_CODE:
                raise
            # $inc on an existing integer never changes BSON size.
            inc = update_ops.get("$inc", {}).get("total-clicks", 1)
            try:
                await self._col.update_one(
                    {"_id": alias}, {"$inc": {"total-clicks": inc}}
                )
            except PyMongoError as retry_exc:
                log.error(
                    "emoji_url_repo_overflow_retry_failed",
                    alias=alias,
                    error=str(retry_exc),
                    error_type=type(retry_exc).__name__,
                )
                raise
            log.info(
                "emoji_url_repo_document_overflow",
                alias=alias,
                msg="document exceeded 16 MB limit; click recorded with total-clicks only",
            )
        except PyMongoError as exc:
            log.error(
                "emoji_url_repo_update_failed",
                alias=alias,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def check_exists(self, alias: str) -> bool:
        """Return True if the emoji alias exists in the collection."""
        try:
            doc = await self._col.find_one({"_id": alias}, {"_id": 1})
            return doc is not None
        except PyMongoError as exc:
            log.error(
                "emoji_url_repo_check_exists_failed",
                alias=alias,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def aggregate(self, pipeline: list[dict]) -> dict[str, Any] | None:
        """
        Run an aggregation pipeline and return the first result document.

        Returns None if the pipeline produces no results (mirrors the legacy
        aggregate_emoji_url() behaviour).
        """
        try:
            cursor = await self._col.aggregate(pipeline)
            results = await cursor.to_list(length=1)
            return results[0] if results else None
        except PyMongoError as exc:
            log.error(
                "emoji_url_repo_aggregate_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise
