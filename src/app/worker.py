"""Celery worker task registration."""

from app.core.celery_app import celery_app


@celery_app.task(name="app.worker.healthcheck")
def healthcheck() -> dict[str, str]:
    """Return a minimal worker readiness signal."""

    return {"status": "ok", "worker": "ready"}


__all__ = ["celery_app", "healthcheck"]
