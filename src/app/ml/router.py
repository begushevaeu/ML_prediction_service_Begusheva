"""ML model API endpoints."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, DbSession
from app.core.errors import not_implemented_error
from app.db.models import MLModel
from app.ml.schemas import MLModelCreate, MLModelListResponse, MLModelRead

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
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Upload a model",
)
def create_model(payload: MLModelCreate, current_user: CurrentUser) -> None:
    """Validate the model-upload contract before storage is implemented."""

    raise not_implemented_error("Model upload is implemented in Step 6.")


__all__ = ["router"]
