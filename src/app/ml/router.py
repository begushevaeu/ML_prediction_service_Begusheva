"""ML model API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, DbSession
from app.core.config import Settings, get_settings
from app.db.models import MLModel
from app.ml.schemas import MLModelListResponse, MLModelRead
from app.ml.service import (
    normalize_framework,
    normalize_model_name,
    parse_metadata_json,
    save_model_upload,
    validate_model_artifact,
)

router = APIRouter(prefix="/models", tags=["models"])


def model_to_read(model: MLModel) -> MLModelRead:
    """Convert a database model row into the public response contract."""

    return MLModelRead(
        id=model.id,
        name=model.name,
        framework=model.framework,
        status=model.status,
        metadata=model.model_metadata,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.get("", response_model=MLModelListResponse, summary="List current user's models")
def list_models(current_user: CurrentUser, session: DbSession) -> MLModelListResponse:
    """Return model metadata owned by the authenticated user."""

    models = (
        session.execute(
            select(MLModel)
            .where(MLModel.owner_id == current_user.id)
            .order_by(MLModel.created_at.desc(), MLModel.id.desc()),
        )
        .scalars()
        .all()
    )
    items = [model_to_read(model) for model in models]
    return MLModelListResponse(items=items, total=len(items))


@router.get(
    "/{model_id}",
    response_model=MLModelRead,
    summary="Get current user's model metadata",
)
def get_model(
    model_id: Annotated[int, Path(gt=0)],
    current_user: CurrentUser,
    session: DbSession,
) -> MLModelRead:
    """Return one owned model metadata row."""

    model = session.scalar(
        select(MLModel).where(MLModel.id == model_id, MLModel.owner_id == current_user.id),
    )
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    return model_to_read(model)


@router.post(
    "",
    response_model=MLModelRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a model",
)
async def create_model(
    name: Annotated[str, Form(min_length=1, max_length=120)],
    file: Annotated[UploadFile, File(description="Scikit-learn .joblib, .pkl, or .pickle file")],
    current_user: CurrentUser,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
    framework: Annotated[str, Form(min_length=1, max_length=50)] = "scikit-learn",
    metadata_json: Annotated[str | None, Form(max_length=5000)] = None,
) -> MLModelRead:
    """Upload, validate, store, and register a model artifact."""

    model_name = normalize_model_name(name)
    normalized_framework = normalize_framework(framework)
    user_metadata = parse_metadata_json(metadata_json)
    saved_path, file_size = await save_model_upload(file, settings, current_user.id)

    try:
        technical_metadata = validate_model_artifact(saved_path, file.filename, file_size)
        model_metadata = {
            **technical_metadata,
            "user_metadata": user_metadata,
        }
        model = MLModel(
            owner_id=current_user.id,
            name=model_name,
            storage_path=str(saved_path),
            framework=normalized_framework,
            status="uploaded",
            model_metadata=model_metadata,
        )
        session.add(model)
        session.commit()
        session.refresh(model)
    except Exception:
        session.rollback()
        saved_path.unlink(missing_ok=True)
        raise

    return model_to_read(model)


__all__ = ["router"]
