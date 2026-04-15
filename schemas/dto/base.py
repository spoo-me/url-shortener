"""
Shared base classes for request and response DTOs.

All DTOs inherit from these to get consistent Pydantic configuration
without repeating ``model_config`` in every class.
"""

from pydantic import BaseModel, ConfigDict


class RequestBase(BaseModel):
    """Base class for all request DTOs."""

    model_config = ConfigDict(populate_by_name=True)


class ResponseBase(BaseModel):
    """Base class for all response DTOs."""

    model_config = ConfigDict(populate_by_name=True)
