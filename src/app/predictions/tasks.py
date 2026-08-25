"""Celery tasks for prediction execution."""

from app.core.celery_app import celery_app
from app.predictions.service import execute_prediction_task


@celery_app.task(name="app.predictions.run_prediction_task")
def run_prediction_task(prediction_id: int) -> dict[str, object]:
    """Run one stored prediction task."""

    return execute_prediction_task(prediction_id)


__all__ = ["run_prediction_task"]
