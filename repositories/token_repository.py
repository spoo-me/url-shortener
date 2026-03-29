"""
Repository for the `verification-tokens` MongoDB collection.

Tokens are used for email verification, password resets, and OTP flows.
All methods are async. Returns VerificationTokenDoc models where applicable.
Errors are logged and re-raised — the service layer decides recovery.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import PyMongoError

from schemas.models.token import VerificationTokenDoc
from shared.logging import get_logger

log = get_logger(__name__)


class TokenRepository:
    def __init__(self, collection: AsyncCollection) -> None:
        self._col = collection

    async def create(self, token_data: dict) -> ObjectId:
        """Insert a new verification token document. Returns the inserted _id."""
        try:
            result = await self._col.insert_one(token_data)
            return result.inserted_id
        except PyMongoError as exc:
            log.error(
                "token_repo_create_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def mark_as_used(self, token_id: ObjectId) -> bool:
        """
        Mark a token as consumed by setting ``used_at`` to now.

        Returns True if a document was modified.
        """
        try:
            result = await self._col.update_one(
                {"_id": token_id},
                {"$set": {"used_at": datetime.now(timezone.utc)}},
            )
            return result.modified_count > 0
        except PyMongoError as exc:
            log.error(
                "token_repo_mark_used_failed",
                token_id=str(token_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def find_latest_by_user(
        self, user_id: ObjectId, token_type: str
    ) -> VerificationTokenDoc | None:
        """Find the most recent non-used token for a user and type."""
        try:
            doc = await self._col.find_one(
                {
                    "user_id": user_id,
                    "token_type": token_type,
                    "used_at": None,
                },
                sort=[("created_at", -1)],
            )
            return VerificationTokenDoc.from_mongo(doc)
        except PyMongoError as exc:
            log.error(
                "token_repo_find_latest_by_user_failed",
                user_id=str(user_id),
                token_type=token_type,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def increment_attempts(self, token_id: ObjectId) -> bool:
        """Atomically increment the ``attempts`` counter on a token.

        Returns True if a document was modified.
        """
        try:
            result = await self._col.update_one(
                {"_id": token_id},
                {"$inc": {"attempts": 1}},
            )
            return result.modified_count > 0
        except PyMongoError as exc:
            log.error(
                "token_repo_increment_attempts_failed",
                token_id=str(token_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def delete_by_user(
        self, user_id: ObjectId, token_type: str | None = None
    ) -> int:
        """
        Delete all tokens for a user, optionally filtered by token type.

        Returns the number of documents deleted.
        """
        query: dict = {"user_id": user_id}
        if token_type is not None:
            query["token_type"] = token_type
        try:
            result = await self._col.delete_many(query)
            return result.deleted_count
        except PyMongoError as exc:
            log.error(
                "token_repo_delete_by_user_failed",
                user_id=str(user_id),
                token_type=token_type,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def count_recent(
        self, user_id: ObjectId, token_type: str, minutes: int = 60
    ) -> int:
        """
        Count tokens created within the last ``minutes`` minutes.

        Used for rate-limiting token issuance (e.g. limit verification
        email resends to N per hour).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        try:
            return await self._col.count_documents(
                {
                    "user_id": user_id,
                    "token_type": token_type,
                    "created_at": {"$gte": cutoff},
                }
            )
        except PyMongoError as exc:
            log.error(
                "token_repo_count_recent_failed",
                user_id=str(user_id),
                token_type=token_type,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise
