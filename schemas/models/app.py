"""
App registry types.

Defines the Pydantic model and enums for app entries loaded from apps.yaml.
Used for YAML validation at startup and typed access throughout the codebase.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AppStatus(str, Enum):
    """App availability status."""

    LIVE = "live"
    COMING_SOON = "coming_soon"


class AppType(str, Enum):
    """App authentication type."""

    DEVICE_AUTH = "device_auth"


class AppEntry(BaseModel):
    """A single app entry from the registry."""

    name: str = Field(min_length=1, max_length=100)
    icon: str | None = None
    description: str = Field(min_length=1, max_length=300)
    verified: bool = False
    status: AppStatus = AppStatus.COMING_SOON
    type: AppType = AppType.DEVICE_AUTH
    redirect_uris: list[str] = []
    links: dict[str, str] = {}
    permissions: list[str] = []

    def is_live_device_app(self) -> bool:
        """Check if this app can participate in the device auth consent flow."""
        return self.status == AppStatus.LIVE and self.type == AppType.DEVICE_AUTH
