"""Prediction API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class PredictionCreate(BaseModel):
    """Contract for a future prediction request."""

    model_id: int = Field(gt=0)
    input_payload: dict[str, object] = Field(default_factory=dict)


class PredictionRead(BaseModel):
    """Public prediction task representation."""

    id: int
    model_id: int
    celery_task_id: str | None
    status: str
    input_payload: dict[str, object] | None
    result_payload: dict[str, object] | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PredictionListResponse(BaseModel):
    """Paginated-style prediction task list response."""

    items: list[PredictionRead]
    total: int


__all__ = ["PredictionCreate", "PredictionListResponse", "PredictionRead"]
