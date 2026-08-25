"""Shared API response schemas."""

from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    """Shared API error body."""

    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    """Shared API error envelope."""

    error: ErrorBody


__all__ = ["ErrorBody", "ErrorResponse"]
