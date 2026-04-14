"""
Repository for the `api-keys` MongoDB collection.

All methods are async. Returns ApiKeyDoc models where applicable.
Errors are handled by BaseRepository.
"""

from __future__ import annotations

from bson import ObjectId
from pymongo.errors import PyMongoError

from repositories.base import BaseRepository
from schemas.models.api_key import ApiKeyDoc
from shared.logging import get_logger

log = get_logger(__name__)


class ApiKeyRepository(BaseRepository[ApiKeyDoc]):
    async def insert(self, doc: dict) -> ObjectId:
        """Insert a new API key document. Returns the inserted _id."""
        return await self._insert(doc)

    async def find_by_hash(self, token_hash: str) -> ApiKeyDoc | None:
        """Find an API key document by its SHA-256 token hash."""
        return await self._find_one({"token_hash": token_hash})

    async def list_by_user(self, user_id: ObjectId) -> list[ApiKeyDoc]:
        """Return all API keys for a user, sorted by creation time ascending."""
        try:
            cursor = self._col.find({"user_id": user_id}).sort("created_at", 1)
            docs = await cursor.to_list(length=None)
            return [ApiKeyDoc.from_mongo(d) for d in docs]  # type: ignore[misc]
        except PyMongoError as exc:
            log.error(
                "repo_list_by_user_failed",
                collection=self._collection_name,
                user_id=str(user_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def revoke(
        self, user_id: ObjectId, key_id: ObjectId, *, hard_delete: bool = False
    ) -> bool:
        """Soft-revoke or hard-delete an API key.

        Returns True if the operation affected a document (ownership check
        is enforced by matching both _id and user_id).
        """
        if hard_delete:
            return await self._delete({"_id": key_id, "user_id": user_id})
        return await self._update(
            {"_id": key_id, "user_id": user_id},
            {"$set": {"revoked": True}},
        )

    async def count_by_user(self, user_id: ObjectId) -> int:
        """Count active (non-revoked) API keys for a user."""
        return await self._count({"user_id": user_id, "revoked": {"$ne": True}})
