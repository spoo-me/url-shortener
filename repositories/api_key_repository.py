"""
Repository for the `api-keys` MongoDB collection.

All methods are async. Returns ApiKeyDoc models where applicable.
Errors are logged and re-raised — the service layer decides recovery.
"""

from __future__ import annotations

from typing import Optional

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError, PyMongoError

from schemas.models.api_key import ApiKeyDoc
from shared.logging import get_logger

log = get_logger(__name__)


class ApiKeyRepository:
    def __init__(self, collection: AsyncCollection) -> None:
        self._col = collection

    async def insert(self, doc: dict) -> ObjectId:
        """Insert a new API key document. Returns the inserted _id."""
        try:
            result = await self._col.insert_one(doc)
            return result.inserted_id
        except DuplicateKeyError as exc:
            log.warning("api_key_repo_insert_duplicate", error=str(exc))
            raise
        except PyMongoError as exc:
            log.error(
                "api_key_repo_insert_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def find_by_hash(self, token_hash: str) -> Optional[ApiKeyDoc]:
        """Find an API key document by its SHA-256 token hash."""
        try:
            doc = await self._col.find_one({"token_hash": token_hash})
            return ApiKeyDoc.from_mongo(doc)  # type: ignore[return-value]
        except PyMongoError as exc:
            log.error(
                "api_key_repo_find_by_hash_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def list_by_user(self, user_id: ObjectId) -> list[ApiKeyDoc]:
        """Return all API keys for a user, sorted by creation time ascending."""
        try:
            cursor = self._col.find({"user_id": user_id}).sort("created_at", 1)
            docs = await cursor.to_list(length=None)
            return [ApiKeyDoc.from_mongo(d) for d in docs]  # type: ignore[misc]
        except PyMongoError as exc:
            log.error(
                "api_key_repo_list_failed",
                user_id=str(user_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def revoke(
        self, user_id: ObjectId, key_id: ObjectId, *, hard_delete: bool = False
    ) -> bool:
        """
        Soft-revoke or hard-delete an API key.

        - hard_delete=False: sets revoked=True on the document.
        - hard_delete=True: removes the document entirely.

        Returns True if the operation affected a document (ownership check
        is enforced by matching both _id and user_id).
        """
        try:
            if hard_delete:
                result = await self._col.delete_one({"_id": key_id, "user_id": user_id})
                return result.deleted_count == 1
            else:
                result = await self._col.update_one(
                    {"_id": key_id, "user_id": user_id},
                    {"$set": {"revoked": True}},
                )
                return result.modified_count == 1
        except PyMongoError as exc:
            log.error(
                "api_key_repo_revoke_failed",
                user_id=str(user_id),
                key_id=str(key_id),
                hard_delete=hard_delete,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def count_by_user(self, user_id: ObjectId) -> int:
        """Count active (non-revoked) API keys for a user."""
        try:
            return await self._col.count_documents(
                {"user_id": user_id, "revoked": {"$ne": True}}
            )
        except PyMongoError as exc:
            log.error(
                "api_key_repo_count_failed",
                user_id=str(user_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise
