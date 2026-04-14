"""
Repository for the `app-grants` MongoDB collection.

Tracks user consent grants for registered apps (device auth flow).
Supports soft-delete via revoked_at for analytics and reconnect flows.
"""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import PyMongoError

from repositories.base import BaseRepository
from schemas.models.app_grant import AppGrantDoc
from shared.logging import get_logger

log = get_logger(__name__)


class AppGrantRepository(BaseRepository[AppGrantDoc]):
    async def find_active_grant(
        self, user_id: ObjectId, app_id: str
    ) -> AppGrantDoc | None:
        """Find an active (non-revoked) grant for a user and app."""
        return await self._find_one(
            {"user_id": user_id, "app_id": app_id, "revoked_at": None}
        )

    async def find_active_for_user(self, user_id: ObjectId) -> list[AppGrantDoc]:
        """Find all active grants for a user."""
        try:
            cursor = self._col.find({"user_id": user_id, "revoked_at": None})
            return [AppGrantDoc.from_mongo(doc) async for doc in cursor]
        except PyMongoError as exc:
            log.error(
                "repo_find_active_for_user_failed",
                collection=self._collection_name,
                user_id=str(user_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def find_all_for_user(self, user_id: ObjectId) -> list[AppGrantDoc]:
        """Find all grants for a user, including revoked."""
        try:
            cursor = self._col.find({"user_id": user_id})
            return [AppGrantDoc.from_mongo(doc) async for doc in cursor]
        except PyMongoError as exc:
            log.error(
                "repo_find_all_for_user_failed",
                collection=self._collection_name,
                user_id=str(user_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def create_or_reactivate(self, user_id: ObjectId, app_id: str) -> AppGrantDoc:
        """Create a new grant or reactivate a revoked one.

        Uses upsert: if a document exists for (user_id, app_id), clears
        revoked_at and updates granted_at. Otherwise inserts a new document.
        """
        now = datetime.now(timezone.utc)
        try:
            doc = await self._col.find_one_and_update(
                {"user_id": user_id, "app_id": app_id},
                {
                    "$set": {
                        "granted_at": now,
                        "revoked_at": None,
                    },
                    "$setOnInsert": {
                        "user_id": user_id,
                        "app_id": app_id,
                        "last_used_at": None,
                    },
                },
                upsert=True,
                return_document=True,
            )
            return AppGrantDoc.from_mongo(doc)  # type: ignore[return-value]
        except PyMongoError as exc:
            log.error(
                "repo_create_or_reactivate_failed",
                collection=self._collection_name,
                user_id=str(user_id),
                app_id=app_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def revoke(self, user_id: ObjectId, app_id: str) -> bool:
        """Soft-delete a grant by setting revoked_at. Returns True if a grant was revoked."""
        return await self._update_modified(
            {"user_id": user_id, "app_id": app_id, "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(timezone.utc)}},
        )

    async def touch_last_used(self, user_id: ObjectId, app_id: str) -> None:
        """Update last_used_at on an active grant."""
        await self._update(
            {"user_id": user_id, "app_id": app_id, "revoked_at": None},
            {"$set": {"last_used_at": datetime.now(timezone.utc)}},
        )
