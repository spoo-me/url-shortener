"""
ProfilePictureService — dashboard profile and profile picture management.

Extracts user profile building and profile picture logic from the route layer.
"""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from errors import NotFoundError
from infrastructure.logging import get_logger
from repositories.user_repository import UserRepository
from schemas.models.user import OAuthProvider, ProfilePicture

log = get_logger(__name__)


class AvailablePicture(BaseModel):
    """A profile picture option from a linked OAuth provider."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique identifier (provider_providerUserId)")
    url: str = Field(description="Picture URL")
    source: OAuthProvider = Field(description="OAuth provider source")
    is_current: bool = Field(description="Whether this is the active picture")


class ProfilePictureService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def get_dashboard_profile(self, user_id: ObjectId) -> dict | None:
        """Fetch a minimal user profile for dashboard template rendering.

        Returns None if the user is not found.
        Matches the shape produced by Flask's utils/auth_utils.get_user_profile().
        """
        user_doc = await self._user_repo.find_by_id(user_id)
        if not user_doc:
            return None

        profile: dict = {
            "id": str(user_doc.id),
            "email": user_doc.email,
            "email_verified": user_doc.email_verified,
            "user_name": user_doc.user_name,
            "plan": user_doc.plan,
            "password_set": user_doc.password_set,
            "auth_providers": [
                {
                    "provider": p.provider,
                    "email": p.email,
                    "linked_at": p.linked_at.isoformat() if p.linked_at else None,
                }
                for p in (user_doc.auth_providers or [])
            ],
        }

        if user_doc.pfp:
            profile["pfp"] = {"url": user_doc.pfp.url, "source": user_doc.pfp.source}

        return profile

    async def get_available_pictures(self, user_id: ObjectId) -> list[AvailablePicture]:
        """Return profile pictures available from connected OAuth providers.

        Raises NotFoundError if the user is not found.
        """
        user_doc = await self._user_repo.find_by_id(user_id)
        if not user_doc:
            raise NotFoundError("User not found")

        current_pfp_url = user_doc.pfp.url if user_doc.pfp else None
        pictures = []
        for provider in user_doc.auth_providers or []:
            picture_url = provider.profile.picture if provider.profile else None
            if picture_url:
                pictures.append(
                    AvailablePicture(
                        id=f"{provider.provider}_{provider.provider_user_id}",
                        url=picture_url,
                        source=provider.provider,
                        is_current=current_pfp_url == picture_url,
                    )
                )
        return pictures

    async def set_picture(self, user_id: ObjectId, picture_id: str) -> None:
        """Set the user's profile picture from an OAuth provider.

        Only allows pictures that exist in the user's auth_providers array.
        Raises NotFoundError if user or picture_id is not found.
        """
        user_doc = await self._user_repo.find_by_id(user_id)
        if not user_doc:
            raise NotFoundError("User not found")

        for provider in user_doc.auth_providers or []:
            provider_id = f"{provider.provider}_{provider.provider_user_id}"
            if provider_id == picture_id:
                picture_url = provider.profile.picture if provider.profile else None
                if picture_url:
                    pfp = ProfilePicture(
                        url=picture_url,
                        source=provider.provider,
                        last_updated=datetime.now(timezone.utc),
                    )
                    await self._user_repo.update(
                        user_id,
                        {"$set": {"pfp": pfp.model_dump()}},
                    )
                    log.info(
                        "profile_picture_updated",
                        user_id=str(user_id),
                        source=provider.provider,
                    )
                    return

        raise NotFoundError("Picture not found")
