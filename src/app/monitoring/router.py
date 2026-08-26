"""Monitoring endpoints."""

from fastapi import APIRouter, Response

from app.auth.dependencies import DbSession
from app.monitoring.metrics import PROMETHEUS_CONTENT_TYPE, render_prometheus_metrics

router = APIRouter(tags=["monitoring"])


@router.get("/metrics", include_in_schema=False)
def get_metrics(session: DbSession) -> Response:
    """Expose Prometheus-compatible metrics for local monitoring."""

    return Response(
        content=render_prometheus_metrics(session),
        media_type=PROMETHEUS_CONTENT_TYPE,
    )


__all__ = ["router"]
