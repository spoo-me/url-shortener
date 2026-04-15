"""
Request DTOs for URL shortening and management endpoints.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

from schemas.dto.base import RequestBase
from schemas.dto.requests._descriptions import LIST_URLS_FILTER_DESC
from schemas.models.url import UrlStatus
from shared.datetime_utils import parse_datetime

ALLOWED_SORT_FIELDS = frozenset({"created_at", "last_click", "total_clicks"})


class UrlFilter(RequestBase):
    """Parsed structure for the ``filter`` query parameter in ListUrlsQuery."""

    status: UrlStatus | None = None
    created_after: str | int | None = Field(
        default=None,
        alias="createdAfter",
        description="Filter URLs created after this time. ISO 8601 string or Unix epoch seconds.",
    )
    created_before: str | int | None = Field(
        default=None,
        alias="createdBefore",
        description="Filter URLs created before this time. ISO 8601 string or Unix epoch seconds.",
    )
    password_set: bool | None = Field(default=None, alias="passwordSet")
    max_clicks_set: bool | None = Field(default=None, alias="maxClicksSet")
    search: str | None = Field(default=None, max_length=500)


class CreateUrlRequest(RequestBase):
    """Request body for creating a new shortened URL.

    Accepts ``url`` as an alias for ``long_url`` — the existing API supports both.
    """

    long_url: str = Field(
        max_length=8192,
        validation_alias=AliasChoices("long_url", "url"),
        description="The destination URL to shorten. Must be a valid http:// or https:// URL.",
        examples=["https://example.com/very/long/url/path"],
    )
    alias: str | None = Field(
        default=None,
        min_length=3,
        max_length=16,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Custom short code. Alphanumeric, hyphens, underscores. 3-16 chars. Auto-generated if omitted.",
        examples=["mylink"],
    )
    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Password to protect the URL. Min 8 chars, must contain letter + number + special char.",
        examples=["secure@123"],
    )
    block_bots: bool | None = Field(
        default=None,
        description="Block known bot user agents from accessing the URL.",
    )
    max_clicks: int | None = Field(
        default=None,
        gt=0,
        description="Maximum clicks before the URL expires. Must be positive.",
        examples=[100],
    )
    expire_after: datetime | None = Field(
        default=None,
        description="Expiration time. ISO 8601 string (e.g. `2025-12-31T23:59:59Z`) or Unix epoch seconds (e.g. `1735689599`).",
        examples=["2025-12-31T23:59:59Z", 1735689599],
    )
    private_stats: bool | None = Field(
        default=None,
        description="Make statistics private (only owner can view). Requires authentication.",
    )

    @field_validator("expire_after", mode="before")
    @classmethod
    def _parse_expire_after(cls, v: str | int | None) -> datetime | None:
        if v is None:
            return None
        result = parse_datetime(v)
        if result is None:
            raise ValueError("Invalid expire_after format")
        return result


class UpdateUrlRequest(RequestBase):
    """Request body for partially updating an existing shortened URL.

    All fields are optional; only provided fields are updated.
    Pass ``max_clicks=0`` or ``max_clicks=null`` to remove the limit.
    Pass ``password=null`` (or omit) to remove password protection.
    """

    long_url: str | None = Field(
        default=None,
        max_length=8192,
        validation_alias=AliasChoices("long_url", "url"),
        description="New destination URL. Must be a valid http:// or https:// URL.",
        examples=["https://example.com/updated/url"],
    )
    alias: str | None = Field(
        default=None,
        min_length=3,
        max_length=16,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="New custom short code. Pass `null` to keep existing. Must be unique and available.",
        examples=["newlink"],
    )
    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="New password. Pass `null` to remove password protection.",
        examples=["newPass@456"],
    )
    block_bots: bool | None = Field(
        default=None,
        description="Block known bot user agents. Pass `null` to keep existing setting.",
    )
    # 0 is allowed here to remove the limit (service layer interprets 0 as "remove")
    max_clicks: int | None = Field(
        default=None,
        ge=0,
        description="New click limit. Pass `0` or `null` to remove the limit.",
        examples=[500],
    )
    expire_after: datetime | None = Field(
        default=None,
        description="Expiration time. ISO 8601 string (e.g. `2025-12-31T23:59:59Z`) or Unix epoch seconds (e.g. `1735689599`). Pass `null` to remove.",
        examples=["2025-12-31T23:59:59Z", 1735689599],
    )
    private_stats: bool | None = Field(
        default=None,
        description="Make statistics private (only owner can view). Pass `null` to keep existing.",
    )
    status: Literal[UrlStatus.ACTIVE, UrlStatus.INACTIVE] | None = Field(
        default=None,
        description="URL status. ACTIVE enables redirects, INACTIVE disables them.",
        examples=["ACTIVE"],
    )

    @field_validator("expire_after", mode="before")
    @classmethod
    def _parse_expire_after(cls, v: str | int | None) -> datetime | None:
        if v is None:
            return None
        result = parse_datetime(v)
        if result is None:
            raise ValueError("Invalid expire_after format")
        return result


class UpdateUrlStatusRequest(BaseModel):
    """Request body for updating only the status of a shortened URL."""

    status: Literal[UrlStatus.ACTIVE, UrlStatus.INACTIVE] = Field(
        description="New status for the URL. `ACTIVE` enables redirects, `INACTIVE` disables them.",
        examples=["ACTIVE"],
    )


class ListUrlsQuery(RequestBase):
    """Query parameters for listing a user's URLs with pagination and filtering.

    The ``filter`` / ``filterBy`` parameter accepts a JSON-encoded ``UrlFilter``
    object.  Call ``get_parsed_filter()`` to obtain the typed sub-model; invalid
    JSON raises ``ValueError`` which FastAPI converts to a 422 response.
    """

    page: int = Field(
        default=1,
        ge=1,
        description="Page number (default: 1)",
        examples=[1],
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        alias="pageSize",
        description="Items per page (default: 20, max: 100)",
        examples=[20],
    )
    sort_by: Literal["created_at", "last_click", "total_clicks"] = Field(
        default="created_at",
        alias="sortBy",
        description="Field to sort by",
    )
    sort_order: Literal["ascending", "asc", "1", "descending", "desc", "-1"] = Field(
        default="descending",
        alias="sortOrder",
        description="Sort direction",
    )
    # Raw JSON string; also accepted as ``filterBy`` (the existing API supports both)
    filter: str | None = Field(
        default=None,
        max_length=10000,
        description=LIST_URLS_FILTER_DESC,
        examples=[
            '{"status":"ACTIVE"}',
            '{"passwordSet": true}',
            '{"createdAfter": "2024-01-01T00:00:00Z"}',
            '{"status": "ACTIVE", "maxClicksSet": true}',
            '{"search": "example"}',
            '{"createdAfter": "2024-01-01", "createdBefore": "2024-12-31", "status": "ACTIVE"}',
        ],
    )
    filter_by: str | None = Field(
        default=None,
        max_length=10000,
        alias="filterBy",
        description="Alias for filter parameter.",
    )
    # Parsed result — populated by the model validator, invisible to FastAPI/OpenAPI
    _parsed_filter: UrlFilter | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _parse_filter_json(self) -> ListUrlsQuery:
        raw = self.filter or self.filter_by
        if not raw:
            return self
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("filter must be valid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("filter must be a JSON object")
        self._parsed_filter = UrlFilter.model_validate(data)
        return self

    @property
    def parsed_filter(self) -> UrlFilter | None:
        return self._parsed_filter
