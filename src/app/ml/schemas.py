"""ML model API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class MLModelCreate(BaseModel):
    """Contract for a future model upload request."""

    name: str = Field(min_length=1, max_length=120)
    framework: str = Field(default="scikit-learn", min_length=1, max_length=50)
    metadata: dict[str, object] | None = None


class MLModelRead(BaseModel):
    """Public ML model metadata."""

    id: int
    name: str
    framework: str
    status: str
    metadata: dict[str, object] | None
    created_at: datetime
    updated_at: datetime


class MLModelListResponse(BaseModel):
    """Paginated-style ML model list response."""

    items: list[MLModelRead]
    total: int


__all__ = ["MLModelCreate", "MLModelListResponse", "MLModelRead"]
