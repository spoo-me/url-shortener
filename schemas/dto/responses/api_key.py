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

from pydantic import BaseModel, ConfigDict


class ApiKeyResponse(BaseModel):
    """A single API key entry as returned by the list endpoint.

    The full token is never returned here — only the ``token_prefix`` for display.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: Optional[str] = None
    scopes: list[str]
    created_at: Optional[int] = None  # Unix timestamp
    expires_at: Optional[int] = None  # Unix timestamp or null
    revoked: bool
    token_prefix: Optional[str] = None


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Response for POST /api/v1/keys (201).

    Extends ApiKeyResponse by adding the full ``token``.  This is the ONLY time
    the token is returned — it is hashed before storage.
    """

    token: str


class ApiKeysListResponse(BaseModel):
    """Response body for GET /api/v1/keys."""

    model_config = ConfigDict(populate_by_name=True)

    keys: list[ApiKeyResponse]


class ApiKeyActionResponse(BaseModel):
    """Response body for DELETE /api/v1/keys/{key_id}."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    action: str  # "deleted" or "revoked"
