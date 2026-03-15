"""
Request DTOs for URL shortening and management endpoints.
"""

from __future__ import annotations

import json
from typing import Literal, Optional, Union

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

ALLOWED_SORT_FIELDS = frozenset({"created_at", "last_click", "total_clicks"})


class UrlFilter(BaseModel):
    """Parsed structure for the ``filter`` query parameter in ListUrlsQuery."""

    model_config = ConfigDict(populate_by_name=True)

    status: Optional[str] = None
    created_after: Optional[Union[str, int]] = Field(
        default=None,
        alias="createdAfter",
        description="Filter URLs created after this time. ISO 8601 string or Unix epoch seconds.",
    )
    created_before: Optional[Union[str, int]] = Field(
        default=None,
        alias="createdBefore",
        description="Filter URLs created before this time. ISO 8601 string or Unix epoch seconds.",
    )
    password_set: Optional[bool] = Field(default=None, alias="passwordSet")
    max_clicks_set: Optional[bool] = Field(default=None, alias="maxClicksSet")
    search: Optional[str] = None


class CreateUrlRequest(BaseModel):
    """Request body for creating a new shortened URL.

    Accepts ``url`` as an alias for ``long_url`` — the existing API supports both.
    """

    model_config = ConfigDict(populate_by_name=True)

    long_url: str = Field(
        validation_alias=AliasChoices("long_url", "url"),
        description="The destination URL to shorten. Must be a valid http:// or https:// URL.",
        examples=["https://example.com/very/long/url/path"],
    )
    alias: Optional[str] = Field(
        default=None,
        description="Custom short code. Alphanumeric, hyphens, underscores. 3-16 chars. Auto-generated if omitted.",
        examples=["mylink"],
    )
    password: Optional[str] = Field(
        default=None,
        description="Password to protect the URL. Min 8 chars, must contain letter + number + special char.",
        examples=["secure@123"],
    )
    block_bots: Optional[bool] = Field(
        default=None,
        description="Block known bot user agents from accessing the URL.",
    )
    max_clicks: Optional[int] = Field(
        default=None,
        gt=0,
        description="Maximum clicks before the URL expires. Must be positive.",
        examples=[100],
    )
    expire_after: Optional[Union[str, int]] = Field(
        default=None,
        description="Expiration time. ISO 8601 string (e.g. `2025-12-31T23:59:59Z`) or Unix epoch seconds (e.g. `1735689599`).",
        examples=["2025-12-31T23:59:59Z", 1735689599],
    )
    private_stats: Optional[bool] = Field(
        default=None,
        description="Make statistics private (only owner can view). Requires authentication.",
    )


class UpdateUrlRequest(BaseModel):
    """Request body for partially updating an existing shortened URL.

    All fields are optional; only provided fields are updated.
    Pass ``max_clicks=0`` or ``max_clicks=null`` to remove the limit.
    Pass ``password=null`` (or omit) to remove password protection.
    """

    model_config = ConfigDict(populate_by_name=True)

    long_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("long_url", "url"),
        description="New destination URL. Must be a valid http:// or https:// URL.",
        examples=["https://example.com/updated/url"],
    )
    alias: Optional[str] = Field(
        default=None,
        description="New custom short code. Pass `null` to keep existing. Must be unique and available.",
        examples=["newlink"],
    )
    password: Optional[str] = Field(
        default=None,
        description="New password. Pass `null` to remove password protection.",
        examples=["newPass@456"],
    )
    block_bots: Optional[bool] = Field(
        default=None,
        description="Block known bot user agents. Pass `null` to keep existing setting.",
    )
    # 0 is allowed here to remove the limit (service layer interprets 0 as "remove")
    max_clicks: Optional[int] = Field(
        default=None,
        ge=0,
        description="New click limit. Pass `0` or `null` to remove the limit.",
        examples=[500],
    )
    expire_after: Optional[Union[str, int]] = Field(
        default=None,
        description="Expiration time. ISO 8601 string (e.g. `2025-12-31T23:59:59Z`) or Unix epoch seconds (e.g. `1735689599`). Pass `null` to remove.",
        examples=["2025-12-31T23:59:59Z", 1735689599],
    )
    private_stats: Optional[bool] = Field(
        default=None,
        description="Make statistics private (only owner can view). Pass `null` to keep existing.",
    )
    status: Optional[Literal["ACTIVE", "INACTIVE"]] = Field(
        default=None,
        description="URL status. ACTIVE enables redirects, INACTIVE disables them.",
        examples=["ACTIVE"],
    )


class ListUrlsQuery(BaseModel):
    """Query parameters for listing a user's URLs with pagination and filtering.

    The ``filter`` / ``filterBy`` parameter accepts a JSON-encoded ``UrlFilter``
    object.  Call ``get_parsed_filter()`` to obtain the typed sub-model; invalid
    JSON raises ``ValueError`` which FastAPI converts to a 422 response.
    """

    model_config = ConfigDict(populate_by_name=True)

    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed).",
        examples=[1],
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        alias="pageSize",
        description="Items per page (1-100).",
        examples=[20],
    )
    sort_by: str = Field(
        default="created_at",
        alias="sortBy",
        description="Sort field. One of: created_at, last_click, total_clicks.",
        examples=["created_at"],
    )
    sort_order: str = Field(
        default="descending",
        alias="sortOrder",
        description="Sort direction: ascending/asc/1 or descending/desc/-1.",
        examples=["descending"],
    )
    # Raw JSON string; also accepted as ``filterBy`` (the existing API supports both)
    filter: Optional[str] = Field(
        default=None,
        description="JSON-encoded filter object. Available fields: status, createdAfter, createdBefore, passwordSet, maxClicksSet, search.",
        examples=['{"status":"ACTIVE"}'],
    )
    filter_by: Optional[str] = Field(
        default=None,
        alias="filterBy",
        description="Alias for filter parameter.",
    )
    # Parsed result — populated by the model validator, invisible to FastAPI/OpenAPI
    _parsed_filter: Optional[UrlFilter] = PrivateAttr(default=None)

    @field_validator("sort_by", mode="after")
    @classmethod
    def _validate_sort_by(cls, v: str) -> str:
        return v if v in ALLOWED_SORT_FIELDS else "created_at"

    @model_validator(mode="after")
    def _parse_filter_json(self) -> "ListUrlsQuery":
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
    def parsed_filter(self) -> Optional[UrlFilter]:
        return self._parsed_filter
