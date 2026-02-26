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

from pydantic import BaseModel, ConfigDict


class UrlResponse(BaseModel):
    """Response body for a newly created shortened URL (POST /api/v1/shorten).

    ``created_at`` is a Unix timestamp integer — matching the existing endpoint.
    """

    model_config = ConfigDict(populate_by_name=True)

    alias: str
    short_url: str
    long_url: str
    owner_id: Optional[str] = None
    created_at: int  # Unix timestamp
    status: str
    private_stats: Optional[bool] = None


class UpdateUrlResponse(BaseModel):
    """Response body after a successful URL update (PATCH /api/v1/urls/{url_id})."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    alias: Optional[str] = None
    long_url: Optional[str] = None
    status: Optional[str] = None
    password_set: bool
    max_clicks: Optional[int] = None
    expire_after: Optional[int] = None  # Unix timestamp or null
    block_bots: Optional[bool] = None
    private_stats: Optional[bool] = None
    updated_at: int  # Unix timestamp


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
