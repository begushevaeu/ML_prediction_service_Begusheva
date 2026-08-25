"""Prediction API endpoints."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, DbSession
from app.core.errors import not_implemented_error
from app.db.models import PredictionTask
from app.predictions.schemas import PredictionCreate, PredictionListResponse, PredictionRead

router = APIRouter(prefix="/predictions", tags=["predictions"])


def prediction_to_read(prediction: PredictionTask) -> PredictionRead:
    """Convert a prediction task row into the public response contract."""

    return PredictionRead(
        id=prediction.id,
        model_id=prediction.model_id,
        status=prediction.status,
        input_payload=prediction.input_payload,
        result_payload=prediction.result_payload,
        error_message=prediction.error_message,
        started_at=prediction.started_at,
        completed_at=prediction.completed_at,
        created_at=prediction.created_at,
        updated_at=prediction.updated_at,
    )


@router.get("", response_model=PredictionListResponse, summary="List prediction tasks")
def list_predictions(
    current_user: CurrentUser,
    session: DbSession,
) -> PredictionListResponse:
    """Return prediction tasks owned by the authenticated user."""

    predictions = (
        session.execute(
            select(PredictionTask)
            .where(PredictionTask.user_id == current_user.id)
            .order_by(PredictionTask.created_at.desc(), PredictionTask.id.desc()),
        )
        .scalars()
        .all()
    )
    items = [prediction_to_read(prediction) for prediction in predictions]
    return PredictionListResponse(items=items, total=len(items))


@router.get(
    "/{prediction_id}",
    response_model=PredictionRead,
    summary="Get a prediction task",
)
def get_prediction(
    prediction_id: Annotated[int, Path(gt=0)],
    current_user: CurrentUser,
    session: DbSession,
) -> PredictionRead:
    """Return one owned prediction task."""

    prediction = session.scalar(
        select(PredictionTask).where(
            PredictionTask.id == prediction_id,
            PredictionTask.user_id == current_user.id,
        ),
    )
    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction task not found",
        )

    return prediction_to_read(prediction)


@router.post(
    "",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Create a prediction task",
)
def create_prediction(payload: PredictionCreate, current_user: CurrentUser) -> None:
    """Validate the prediction request contract before execution is implemented."""

    raise not_implemented_error("Prediction execution is implemented in Step 7.")


__all__ = ["router"]
