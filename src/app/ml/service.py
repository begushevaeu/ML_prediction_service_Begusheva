"""ML model upload and validation helpers."""

import json
import pickle
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings

ALLOWED_MODEL_EXTENSIONS = {".joblib", ".pkl", ".pickle"}
UPLOAD_CHUNK_SIZE_BYTES = 1024 * 1024
VALIDATION_ERROR_STATUS_CODE = 422
CONTENT_TOO_LARGE_STATUS_CODE = 413


class ModelArtifactError(ValueError):
    """Raised when a stored model artifact cannot be used for prediction."""


def normalize_model_name(value: str) -> str:
    """Normalize a user-visible model name."""

    name = value.strip()
    if not name:
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS_CODE,
            detail={"code": "validation_error", "message": "Model name is required"},
        )
    return name


def normalize_framework(value: str) -> str:
    """Normalize the model framework field."""

    framework = value.strip()
    if not framework:
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS_CODE,
            detail={"code": "validation_error", "message": "Model framework is required"},
        )
    return framework


def parse_metadata_json(value: str | None) -> dict[str, Any] | None:
    """Parse optional user metadata from a multipart form field."""

    if value is None or not value.strip():
        return None

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS_CODE,
            detail={"code": "validation_error", "message": "metadata_json must be valid JSON"},
        ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS_CODE,
            detail={"code": "validation_error", "message": "metadata_json must be a JSON object"},
        )

    return parsed


def _suffix_for_upload(upload: UploadFile) -> str:
    filename = Path(upload.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_MODEL_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "code": "unsupported_model_file",
                "message": "Model file must have .joblib, .pkl, or .pickle extension",
            },
        )
    return suffix


async def save_model_upload(
    upload: UploadFile, settings: Settings, owner_id: int
) -> tuple[Path, int]:
    """Save an uploaded model file and enforce the configured size limit."""

    suffix = _suffix_for_upload(upload)
    owner_dir = Path(settings.model_storage_path).expanduser() / str(owner_id)
    owner_dir.mkdir(parents=True, exist_ok=True)

    destination = owner_dir / f"{uuid4().hex}{suffix}"
    size = 0

    try:
        with destination.open("wb") as buffer:
            while chunk := await upload.read(UPLOAD_CHUNK_SIZE_BYTES):
                size += len(chunk)
                if size > settings.max_model_upload_size_bytes:
                    raise HTTPException(
                        status_code=CONTENT_TOO_LARGE_STATUS_CODE,
                        detail={
                            "code": "model_file_too_large",
                            "message": "Model file exceeds the configured upload limit",
                        },
                    )
                buffer.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    if size == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS_CODE,
            detail={"code": "invalid_model_file", "message": "Model file is empty"},
        )

    return destination, size


def _load_model(path: Path) -> Any:
    joblib_error: Exception | None = None
    try:
        import joblib
    except ModuleNotFoundError:
        joblib = None

    if joblib is not None:
        try:
            return joblib.load(path)
        except Exception as exc:  # noqa: BLE001
            joblib_error = exc

    try:
        with path.open("rb") as model_file:
            return pickle.load(model_file)
    except Exception as exc:
        raise ModelArtifactError("Model file could not be loaded") from (joblib_error or exc)


def load_model_artifact(path: Path) -> Any:
    """Load a stored model artifact and ensure it exposes predict."""

    model = _load_model(path)
    predict = getattr(model, "predict", None)
    if not callable(predict):
        raise ModelArtifactError("Model object must define a callable predict method")

    return model


def validate_model_artifact(
    path: Path, original_filename: str | None, file_size_bytes: int
) -> dict[str, Any]:
    """Load a model artifact and return technical metadata."""

    try:
        model = load_model_artifact(path)
    except ModelArtifactError as exc:
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS_CODE,
            detail={
                "code": "invalid_model_file",
                "message": str(exc),
            },
        ) from exc

    model_type = f"{model.__class__.__module__}.{model.__class__.__name__}"
    return {
        "uploaded_filename": Path(original_filename or "").name or None,
        "file_size_bytes": file_size_bytes,
        "model_type": model_type,
    }


__all__ = [
    "ALLOWED_MODEL_EXTENSIONS",
    "ModelArtifactError",
    "load_model_artifact",
    "normalize_framework",
    "normalize_model_name",
    "parse_metadata_json",
    "save_model_upload",
    "validate_model_artifact",
]
