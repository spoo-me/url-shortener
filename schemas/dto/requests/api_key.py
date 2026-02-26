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

    name: str
    description: Optional[str] = None
    scopes: list[str]
    # ISO 8601 string or Unix epoch seconds; null means no expiration
    expires_at: Optional[Union[str, int, float]] = None

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
