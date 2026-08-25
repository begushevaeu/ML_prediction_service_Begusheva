"""Celery application factory for asynchronous workers."""

from celery import Celery

from app.core.config import Settings, get_settings


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Create the Celery application used by worker containers."""

    resolved_settings = settings or get_settings()
    celery_app = Celery(
        "ml_prediction_service",
        broker=resolved_settings.redis_url,
        backend=resolved_settings.redis_url,
        include=["app.worker"],
    )
    celery_app.conf.update(
        accept_content=["json"],
        enable_utc=True,
        result_serializer="json",
        task_serializer="json",
        task_track_started=True,
        timezone="UTC",
    )
    return celery_app


celery_app = create_celery_app()

__all__ = ["celery_app", "create_celery_app"]
