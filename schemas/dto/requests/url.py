"""
Request DTOs for URL shortening and management endpoints.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Optional, Union

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

ALLOWED_SORT_FIELDS = frozenset({"created_at", "last_click", "total_clicks"})


class UrlFilter(BaseModel):
    """Parsed structure for the ``filter`` query parameter in ListUrlsQuery."""

    model_config = ConfigDict(populate_by_name=True)

    status: Optional[str] = None
    created_after: Optional[Any] = Field(default=None, alias="createdAfter")
    created_before: Optional[Any] = Field(default=None, alias="createdBefore")
    password_set: Optional[bool] = Field(default=None, alias="passwordSet")
    max_clicks_set: Optional[bool] = Field(default=None, alias="maxClicksSet")
    search: Optional[str] = None


class CreateUrlRequest(BaseModel):
    """Request body for creating a new shortened URL.

    Accepts ``url`` as an alias for ``long_url`` — the existing API supports both.
    """

    model_config = ConfigDict(populate_by_name=True)

    long_url: str = Field(validation_alias=AliasChoices("long_url", "url"))
    alias: Optional[str] = None
    password: Optional[str] = None
    block_bots: Optional[bool] = None
    max_clicks: Optional[int] = Field(default=None, gt=0)
    # ISO 8601 string or Unix epoch seconds — service layer does the conversion
    expire_after: Optional[Union[str, int, float]] = None
    private_stats: Optional[bool] = None


class UpdateUrlRequest(BaseModel):
    """Request body for partially updating an existing shortened URL.

    All fields are optional; only provided fields are updated.
    Pass ``max_clicks=0`` or ``max_clicks=null`` to remove the limit.
    Pass ``password=null`` (or omit) to remove password protection.
    """

    model_config = ConfigDict(populate_by_name=True)

    long_url: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("long_url", "url")
    )
    alias: Optional[str] = None
    password: Optional[str] = None
    block_bots: Optional[bool] = None
    # 0 is allowed here to remove the limit (service layer interprets 0 as "remove")
    max_clicks: Optional[int] = Field(default=None, ge=0)
    expire_after: Optional[Union[str, int, float]] = None
    private_stats: Optional[bool] = None
    status: Optional[Literal["ACTIVE", "INACTIVE"]] = None


class ListUrlsQuery(BaseModel):
    """Query parameters for listing a user's URLs with pagination and filtering.

    The ``filter`` / ``filterBy`` parameter accepts a JSON-encoded ``UrlFilter``
    object.  Call ``get_parsed_filter()`` to obtain the typed sub-model; invalid
    JSON raises ``ValueError`` which FastAPI converts to a 422 response.
    """

    model_config = ConfigDict(populate_by_name=True)

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100, alias="pageSize")
    sort_by: str = Field(default="created_at", alias="sortBy")
    sort_order: str = Field(default="descending", alias="sortOrder")
    # Raw JSON string; also accepted as ``filterBy`` (the existing API supports both)
    filter: Optional[str] = None
    filter_by: Optional[str] = Field(default=None, alias="filterBy")
    # Parsed result — populated by the model validator, excluded from serialization
    parsed_filter: Optional[UrlFilter] = Field(default=None, exclude=True)

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
        self.parsed_filter = UrlFilter.model_validate(data)
        return self
