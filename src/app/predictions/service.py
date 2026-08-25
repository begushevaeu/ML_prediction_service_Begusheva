"""Prediction execution helpers."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import PredictionTask
from app.db.session import SessionLocal
from app.ml.service import load_model_artifact

VALIDATION_ERROR_STATUS_CODE = 422


class PredictionInputError(ValueError):
    """Raised when prediction input payload cannot be used."""


def extract_prediction_rows(input_payload: dict[str, object] | None) -> list[object]:
    """Read the MVP rows contract from a prediction input payload."""

    if not input_payload or "rows" not in input_payload:
        raise PredictionInputError("input_payload.rows is required")

    rows = input_payload["rows"]
    if not isinstance(rows, list) or not rows:
        raise PredictionInputError("input_payload.rows must be a non-empty list")

    return rows


def validate_prediction_input_payload(input_payload: dict[str, object] | None) -> None:
    """Raise a public API validation error for invalid prediction input."""

    try:
        extract_prediction_rows(input_payload)
    except PredictionInputError as exc:
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS_CODE,
            detail={"code": "validation_error", "message": str(exc)},
        ) from exc


def make_json_compatible(value: Any) -> Any:
    """Convert model output into JSON-compatible values."""

    if hasattr(value, "tolist"):
        return make_json_compatible(value.tolist())

    if isinstance(value, dict):
        return {str(key): make_json_compatible(item) for key, item in value.items()}

    if isinstance(value, list | tuple):
        return [make_json_compatible(item) for item in value]

    if isinstance(value, str | int | float | bool) or value is None:
        return value

    return str(value)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def execute_prediction_task(
    prediction_id: int,
    session_factory: Callable[[], Session] = SessionLocal,
) -> dict[str, object]:
    """Execute a stored prediction task and persist its final status."""

    with session_factory() as session:
        prediction = session.get(PredictionTask, prediction_id)
        if prediction is None:
            return {"prediction_id": prediction_id, "status": "missing"}

        prediction.status = "running"
        prediction.started_at = _utc_now()
        session.commit()
        session.refresh(prediction)

        try:
            model = load_model_artifact(Path(prediction.model.storage_path))
            rows = extract_prediction_rows(prediction.input_payload)
            raw_result = model.predict(rows)
            prediction.result_payload = {"predictions": make_json_compatible(raw_result)}
            prediction.error_message = None
            prediction.status = "succeeded"
        except Exception as exc:  # noqa: BLE001
            prediction.result_payload = None
            prediction.error_message = str(exc)
            prediction.status = "failed"

        prediction.completed_at = _utc_now()
        session.commit()

        return {
            "prediction_id": prediction_id,
            "status": prediction.status,
            "error": prediction.error_message,
        }


__all__ = [
    "PredictionInputError",
    "execute_prediction_task",
    "extract_prediction_rows",
    "make_json_compatible",
    "validate_prediction_input_payload",
]
