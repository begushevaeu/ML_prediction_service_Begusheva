"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    resolved_settings = settings or get_settings()
    application = FastAPI(
        title=resolved_settings.app_name,
        debug=resolved_settings.app_debug,
        version="0.1.0",
    )
    application.state.settings = resolved_settings

    application.include_router(api_router, prefix=resolved_settings.api_v1_prefix)

    @application.get("/", tags=["system"], summary="Service metadata")
    def root() -> dict[str, str]:
        return {
            "service": resolved_settings.app_name,
            "status": "ready",
        }

    return application


app = create_app()

__all__ = ["app", "create_app"]
