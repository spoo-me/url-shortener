"""
Repository for the `users` MongoDB collection.

All methods are async and return typed Pydantic document models (UserDoc).
Errors are logged and re-raised — the service layer decides recovery.
"""

from __future__ import annotations

from typing import Optional

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError, PyMongoError

from schemas.models.user import UserDoc
from shared.logging import get_logger

log = get_logger(__name__)


class UserRepository:
    def __init__(self, collection: AsyncCollection) -> None:
        self._col = collection

    async def find_by_email(self, email: str) -> Optional[UserDoc]:
        """Find a user by email address."""
        try:
            doc = await self._col.find_one({"email": email})
            return UserDoc.from_mongo(doc)
        except PyMongoError as exc:
            log.error(
                "user_repo_find_by_email_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def find_by_id(self, user_id: ObjectId) -> Optional[UserDoc]:
        """Find a user by ObjectId."""
        try:
            doc = await self._col.find_one({"_id": user_id})
            return UserDoc.from_mongo(doc)
        except PyMongoError as exc:
            log.error(
                "user_repo_find_by_id_failed",
                user_id=str(user_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def find_by_oauth_provider(
        self, provider: str, provider_user_id: str
    ) -> Optional[UserDoc]:
        """
        Find a user by their OAuth provider and provider-issued user ID.

        Queries the nested auth_providers array.
        """
        try:
            doc = await self._col.find_one(
                {
                    "auth_providers.provider": provider,
                    "auth_providers.provider_user_id": provider_user_id,
                }
            )
            return UserDoc.from_mongo(doc)
        except PyMongoError as exc:
            log.error(
                "user_repo_find_by_oauth_failed",
                provider=provider,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def create(self, user_data: dict) -> ObjectId:
        """Insert a new user document. Returns the inserted _id."""
        try:
            result = await self._col.insert_one(user_data)
            return result.inserted_id
        except DuplicateKeyError as exc:
            log.warning(
                "user_repo_create_duplicate",
                email=user_data.get("email"),
                error=str(exc),
            )
            raise
        except PyMongoError as exc:
            log.error(
                "user_repo_create_failed",
                email=user_data.get("email"),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    async def update(self, user_id: ObjectId, update_ops: dict) -> bool:
        """
        Apply a MongoDB update document to a user.

        Returns True if the document was matched.
        """
        try:
            result = await self._col.update_one({"_id": user_id}, update_ops)
            return result.matched_count > 0
        except PyMongoError as exc:
            log.error(
                "user_repo_update_failed",
                user_id=str(user_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise
