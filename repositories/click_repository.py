"""
Repository for the `clicks` MongoDB time-series collection.

The clicks collection has a strict schema requirement:
  - timeField: "clicked_at"  (datetime)
  - metaField: "meta"        (ClickMeta subdoc with url_id, short_code, owner_id)

All aggregation pipelines are passed in from the service layer — the repository
does not build pipelines itself.
"""

from __future__ import annotations

from typing import Any

from pymongo.errors import PyMongoError

from infrastructure.logging import get_logger
from repositories.base import BaseRepository

log = get_logger(__name__)


class ClickRepository(BaseRepository[None]):
    async def insert(self, doc: dict) -> None:
        """Insert a click document into the time-series collection.

        The caller (click service) is responsible for constructing a valid
        document via ClickDoc.to_mongo(), which guarantees the required
        `meta` and `clicked_at` fields are present.
        """
        try:
            await self._col.insert_one(doc)
        except PyMongoError as exc:
            log.error(
                "repo_insert_failed",
                collection=self._collection_name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def aggregate(self, pipeline: list[dict]) -> list[dict[str, Any]]:
        """Run an aggregation pipeline against the clicks collection.

        The pipeline is built by the stats service (supports $facet for
        multiple simultaneous aggregations). Returns the full result list.
        """
        return await self._aggregate(pipeline)
