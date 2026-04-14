"""
Repository for the `users` MongoDB collection.

All methods are async and return typed Pydantic document models (UserDoc).
Errors are handled by BaseRepository.
"""

from __future__ import annotations

from bson import ObjectId

from repositories.base import BaseRepository
from schemas.models.user import UserDoc


class UserRepository(BaseRepository[UserDoc]):
    async def find_by_email(self, email: str) -> UserDoc | None:
        """Find a user by email address."""
        return await self._find_one({"email": email})

    async def find_by_id(self, user_id: ObjectId) -> UserDoc | None:
        """Find a user by ObjectId."""
        return await self._find_one({"_id": user_id})

    async def find_by_oauth_provider(
        self, provider: str, provider_user_id: str
    ) -> UserDoc | None:
        """Find a user by their OAuth provider and provider-issued user ID.

        Uses ``$elemMatch`` to ensure both fields match the same array
        element — without it, MongoDB can satisfy each condition from
        different elements when a user has multiple linked providers.
        """
        return await self._find_one(
            {
                "auth_providers": {
                    "$elemMatch": {
                        "provider": provider,
                        "provider_user_id": provider_user_id,
                    }
                }
            }
        )

    async def create(self, user_data: dict) -> ObjectId:
        """Insert a new user document. Returns the inserted _id."""
        return await self._insert(user_data)

    async def update(self, user_id: ObjectId, update_ops: dict) -> bool:
        """Apply a MongoDB update document to a user.

        Returns True if the document was matched.
        """
        return await self._update({"_id": user_id}, update_ops)
