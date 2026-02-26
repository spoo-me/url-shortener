"""
Common response DTOs shared across multiple endpoints.

ErrorResponse    — standard error shape from AppError.to_dict()
HealthResponse   — GET /health
MessageResponse  — generic {success, message} shape used by many endpoints
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    """Standard error JSON body produced by the AppError exception handler."""

    model_config = ConfigDict(populate_by_name=True)

    error: str
    error_code: str
    field: Optional[str] = None
    details: Optional[Any] = None


class HealthChecks(BaseModel):
    """Individual service check statuses inside HealthResponse."""

    model_config = ConfigDict(populate_by_name=True)

    mongodb: str
    redis: str


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    model_config = ConfigDict(populate_by_name=True)

    status: str
    checks: dict[str, str]


class MessageResponse(BaseModel):
    """Generic success/message response returned by several endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    message: Optional[str] = None


class PaginationMeta(BaseModel):
    """Reusable pagination metadata included in list responses."""

    model_config = ConfigDict(populate_by_name=True)

    page: int
    page_size: int
    total: int
    has_next: bool
