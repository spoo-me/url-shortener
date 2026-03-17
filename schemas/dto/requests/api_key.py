"""
Request DTOs for API key management endpoints.

CreateApiKeyRequest — POST /api/v1/keys
"""

from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_SCOPES = frozenset(
    {
        "shorten:create",
        "urls:manage",
        "urls:read",
        "stats:read",
        "admin:all",
    }
)


class CreateApiKeyRequest(BaseModel):
    """Request body for POST /api/v1/keys."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(
        description="Human-readable key name",
        examples=["My Production Key"],
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional description of what this key is used for",
        examples=["Used by the mobile app for URL shortening"],
    )
    scopes: list[str] = Field(
        description="Permission scopes for the key",
        examples=[["shorten:create", "stats:read"]],
    )
    expires_at: Optional[Union[str, int]] = Field(
        default=None,
        description="Expiration time. ISO 8601 string (e.g. `2026-01-01T00:00:00Z`) or Unix epoch seconds (e.g. `1735689599`). Omit for non-expiring key.",
        examples=["2026-01-01T00:00:00Z", 1735689599],
    )

    @field_validator("name", mode="after")
    @classmethod
    def _name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name is required")
        return v

    @field_validator("scopes", mode="after")
    @classmethod
    def _validate_scopes(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("scopes must be a non-empty array")
        invalid = set(v) - ALLOWED_SCOPES
        if invalid:
            raise ValueError(f"invalid scope(s): {', '.join(invalid)}")
        return v
