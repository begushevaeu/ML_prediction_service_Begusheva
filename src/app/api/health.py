"""Health-check API endpoints."""

from fastapi import APIRouter, Request

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health check")
def health_check(request: Request) -> dict[str, str]:
    """Return a minimal readiness signal for local development."""

    settings = getattr(request.app.state, "settings", get_settings())
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }
