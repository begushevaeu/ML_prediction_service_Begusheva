"""Prediction API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, DbSession
from app.billing.service import InsufficientCreditsError, require_sufficient_credits
from app.core.config import Settings, get_settings
from app.db.models import MLModel, PredictionTask
from app.predictions.schemas import PredictionCreate, PredictionListResponse, PredictionRead
from app.predictions.service import validate_prediction_input_payload
from app.predictions.tasks import run_prediction_task

router = APIRouter(prefix="/predictions", tags=["predictions"])


def prediction_to_read(prediction: PredictionTask) -> PredictionRead:
    """Convert a prediction task row into the public response contract."""

    return PredictionRead(
        id=prediction.id,
        model_id=prediction.model_id,
        celery_task_id=prediction.celery_task_id,
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
    response_model=PredictionRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a prediction task",
)
def create_prediction(
    payload: PredictionCreate,
    current_user: CurrentUser,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PredictionRead:
    """Create a prediction task and enqueue asynchronous execution."""

    model = session.scalar(
        select(MLModel).where(
            MLModel.id == payload.model_id,
            MLModel.owner_id == current_user.id,
            MLModel.status == "uploaded",
        ),
    )
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    validate_prediction_input_payload(payload.input_payload)
    try:
        require_sufficient_credits(
            session,
            current_user.id,
            settings.prediction_price_credits,
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "insufficient_credits",
                "message": str(exc),
                "details": {"available": exc.available, "required": exc.required},
            },
        ) from exc

    prediction = PredictionTask(
        user_id=current_user.id,
        model_id=model.id,
        status="queued",
        input_payload=payload.input_payload,
    )
    session.add(prediction)
    session.commit()
    session.refresh(prediction)

    async_result = run_prediction_task.delay(prediction.id)
    prediction.celery_task_id = async_result.id
    session.commit()
    session.refresh(prediction)

    return prediction_to_read(prediction)


__all__ = ["router"]
