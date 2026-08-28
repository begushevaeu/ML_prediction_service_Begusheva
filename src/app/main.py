"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.api.schemas import ErrorResponse
from app.core.config import Settings, get_settings, validate_security_settings
from app.core.errors import http_exception_handler, validation_exception_handler
from app.db.session import SessionLocal
from app.monitoring.metrics import record_http_request
from app.monitoring.router import router as monitoring_router
from app.users.service import ensure_local_admin_user, ensure_local_demo_users


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    resolved_settings = settings or get_settings()
    validate_security_settings(resolved_settings)

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        if resolved_settings.bootstrap_local_admin:
            with SessionLocal() as session:
                ensure_local_admin_user(session, resolved_settings)
                ensure_local_demo_users(session, resolved_settings)
        yield

    application = FastAPI(
        title=resolved_settings.app_name,
        debug=resolved_settings.app_debug,
        version="0.1.0",
        lifespan=lifespan,
        responses={
            status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
            status.HTTP_402_PAYMENT_REQUIRED: {"model": ErrorResponse},
            status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
            status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
            status.HTTP_409_CONFLICT: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            status.HTTP_501_NOT_IMPLEMENTED: {"model": ErrorResponse},
        },
    )
    application.state.settings = resolved_settings

    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)

    @application.middleware("http")
    async def record_request_metrics(request: Request, call_next):
        started_at = perf_counter()
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            record_http_request(
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_seconds=perf_counter() - started_at,
            )

    application.include_router(api_router, prefix=resolved_settings.api_v1_prefix)
    application.include_router(monitoring_router)

    @application.get("/", tags=["system"], summary="Service metadata")
    def root() -> dict[str, str]:
        return {
            "service": resolved_settings.app_name,
            "status": "ready",
        }

    return application


app = create_app()

__all__ = ["app", "create_app"]
