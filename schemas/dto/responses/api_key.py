"""
Response DTOs for API key management endpoints.

ApiKeyResponse        — one key entry in GET /api/v1/keys list
ApiKeyCreatedResponse — POST /api/v1/keys (201) — includes ``token`` once
ApiKeysListResponse   — GET /api/v1/keys (200)
ApiKeyActionResponse  — DELETE /api/v1/keys/{key_id} (200)

``created_at`` and ``expires_at`` are Unix timestamp integers — matching the
existing Flask endpoint exactly.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyResponse(BaseModel):
    """A single API key entry as returned by the list endpoint.

    The full token is never returned here — only the ``token_prefix`` for display.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="API key ID", examples=["507f1f77bcf86cd799439011"])
    name: str = Field(
        description="Human-readable key name", examples=["My Production Key"]
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional description",
        examples=["Used by the mobile app"],
    )
    scopes: list[str] = Field(
        description="Permission scopes granted to this key",
        examples=[["shorten:create", "stats:read"]],
    )
    created_at: Optional[int] = Field(
        default=None,
        description="Creation time as Unix timestamp",
        examples=[1704067200],
    )
    expires_at: Optional[int] = Field(
        default=None,
        description="Expiration time as Unix timestamp, or null if no expiration",
        examples=[1735689600],
    )
    revoked: bool = Field(description="Whether the key has been revoked")
    token_prefix: Optional[str] = Field(
        default=None,
        description="First characters of the token for identification",
        examples=["spoo_abc1"],
    )


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Response for POST /api/v1/keys (201).

    Extends ApiKeyResponse by adding the full ``token``.  This is the ONLY time
    the token is returned — it is hashed before storage.
    """

    token: str = Field(
        description="Full API key token (only returned once at creation time)",
        examples=["spoo_abc123def456ghi789"],
    )


class ApiKeysListResponse(BaseModel):
    """Response body for GET /api/v1/keys."""

    model_config = ConfigDict(populate_by_name=True)

    keys: list[ApiKeyResponse] = Field(
        description="List of API keys for the authenticated user"
    )


class ApiKeyActionResponse(BaseModel):
    """Response body for DELETE /api/v1/keys/{key_id}."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool = Field(description="Whether the action completed successfully")
    action: str = Field(
        description="Action that was performed",
        examples=["deleted"],
    )
