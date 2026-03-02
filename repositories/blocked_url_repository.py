"""
Repository for the `blocked-urls` MongoDB collection.

The collection stores regex patterns used to block malicious/spam URLs.
Patterns are loaded via get_patterns() which should be called by the service
layer with appropriate caching — this repository does NOT cache results.

All methods are async. Errors are logged and re-raised.
"""

from __future__ import annotations

from pymongo.asynchronous.collection import AsyncCollection

from shared.logging import get_logger

log = get_logger(__name__)


class BlockedUrlRepository:
    def __init__(self, collection: AsyncCollection) -> None:
        self._col = collection

    async def get_patterns(self) -> list[str]:
        """
        Return all blocked URL regex patterns from the collection.

        Each document's ``_id`` is the pattern string (as in the legacy
        _fetch_blocked_patterns() function).
        """
        try:
            cursor = self._col.find({}, {"_id": 1})
            docs = await cursor.to_list(length=None)
            return [doc["_id"] for doc in docs]
        except Exception as exc:
            log.error("blocked_url_repo_get_patterns_failed", error=str(exc))
            raise
