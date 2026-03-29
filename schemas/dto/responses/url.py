"""
Response DTOs for URL shortening and management endpoints.

UrlResponse       — POST /api/v1/shorten  (201)
UpdateUrlResponse — PATCH /api/v1/urls/{url_id}  (200)
UrlListItem       — one element inside UrlListResponse.items
UrlListResponse   — GET /api/v1/urls  (200)

Response shapes are the API contract — field names match the existing Flask
endpoints exactly, including the camelCase keys in UrlListResponse
(``pageSize``, ``hasNext``, ``sortBy``, ``sortOrder``).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UrlResponse(BaseModel):
    """Response body for a newly created shortened URL (POST /api/v1/shorten).

    ``created_at`` is a Unix timestamp integer — matching the existing endpoint.
    """

    model_config = ConfigDict(populate_by_name=True)

    alias: str = Field(description="Short code for the URL.", examples=["mylink"])
    short_url: str = Field(
        description="Full shortened URL ready for sharing.",
        examples=["https://spoo.me/mylink"],
    )
    long_url: str = Field(
        description="Original destination URL.",
        examples=["https://example.com/long/url"],
    )
    owner_id: Optional[str] = Field(
        default=None,
        description="User ID if authenticated, null for anonymous URLs.",
        examples=["507f1f77bcf86cd799439011"],
    )
    created_at: int = Field(
        description="Creation time as Unix timestamp.",
        examples=[1704067200],
    )
    status: str = Field(description="URL status.", examples=["ACTIVE"])
    private_stats: Optional[bool] = Field(
        default=None,
        description="Whether statistics are private (owner-only).",
    )
    manage_token: Optional[str] = Field(
        default=None,
        description="Returned once for anonymous URLs only. Never stored in plaintext.",
        examples=["kS9_x1z..."],
    )



class UpdateUrlResponse(BaseModel):
    """Response body after a successful URL update (PATCH /api/v1/urls/{url_id})."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        description="MongoDB ObjectId of the URL.",
        examples=["507f1f77bcf86cd799439011"],
    )
    alias: Optional[str] = Field(
        default=None, description="Short code.", examples=["mylink"]
    )
    long_url: Optional[str] = Field(
        default=None,
        description="Destination URL.",
        examples=["https://example.com/long/url"],
    )
    status: Optional[str] = Field(
        default=None, description="URL status.", examples=["ACTIVE"]
    )
    password_set: bool = Field(description="Whether the URL is password-protected.")
    max_clicks: Optional[int] = Field(
        default=None, description="Click limit, or null if unlimited.", examples=[100]
    )
    expire_after: Optional[int] = Field(
        default=None,
        description="Expiration as Unix timestamp, or null.",
        examples=[1735689599],
    )
    block_bots: Optional[bool] = Field(
        default=None, description="Whether bot blocking is enabled."
    )
    private_stats: Optional[bool] = Field(
        default=None, description="Whether statistics are private."
    )
    updated_at: int = Field(
        description="Last update time as Unix timestamp.", examples=[1704067200]
    )


class UrlListItem(BaseModel):
    """A single URL entry inside UrlListResponse.items.

    ``created_at`` and ``last_click`` are ISO 8601 strings (e.g. "2024-01-01T00:00:00Z").
    ``expire_after`` is a Unix timestamp integer or null.
    These formats match the existing endpoint exactly.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    alias: Optional[str] = None
    long_url: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None  # ISO 8601 string
    expire_after: Optional[int] = None  # Unix timestamp or null
    max_clicks: Optional[int] = None
    private_stats: Optional[bool] = None
    block_bots: Optional[bool] = None
    password_set: bool
    total_clicks: Optional[int] = None
    last_click: Optional[str] = None  # ISO 8601 string or null


class DeleteUrlResponse(BaseModel):
    """Response body for DELETE /api/v1/urls/{url_id}."""

    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(description="Confirmation message.", examples=["URL deleted"])
    id: str = Field(
        description="ID of the deleted URL.", examples=["507f1f77bcf86cd799439011"]
    )


class UrlListResponse(BaseModel):
    """Response body for GET /api/v1/urls.

    Uses camelCase field names to match the existing Flask endpoint exactly.
    Field names are camelCase here (not snake_case + alias) because this is a
    response-only model — we build it explicitly in the route handler.
    """

    model_config = ConfigDict(populate_by_name=True)

    items: list[UrlListItem]
    page: int
    pageSize: int
    total: int
    hasNext: bool
    sortBy: str
    sortOrder: str
