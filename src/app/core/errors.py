"""Shared application error types and handlers."""

from http import HTTPStatus
from typing import Any

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base exception for expected application-level errors."""


VALIDATION_ERROR_STATUS_CODE = 422


def build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    """Build the public API error envelope."""

    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = jsonable_encoder(details)

    return {"error": error}


def _message_for_status(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Request failed"


def _normalize_http_detail(status_code: int, detail: Any) -> dict[str, Any]:
    if isinstance(detail, dict):
        code = str(detail.get("code") or status_code)
        message = str(detail.get("message") or _message_for_status(status_code))
        normalized: dict[str, Any] = {"code": code, "message": message}
        if "details" in detail:
            normalized["details"] = detail["details"]
        return normalized

    return {
        "code": str(status_code),
        "message": str(detail or _message_for_status(status_code)),
    }


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Return HTTP errors in the shared API envelope."""

    normalized = _normalize_http_detail(exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(
            status_code=exc.status_code,
            code=normalized["code"],
            message=normalized["message"],
            details=normalized.get("details"),
        ),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return request validation errors in the shared API envelope."""

    return JSONResponse(
        status_code=VALIDATION_ERROR_STATUS_CODE,
        content=build_error_response(
            status_code=VALIDATION_ERROR_STATUS_CODE,
            code="validation_error",
            message="Validation error",
            details=exc.errors(),
        ),
    )


def not_implemented_error(message: str) -> StarletteHTTPException:
    """Build a consistent placeholder error for deferred workflow steps."""

    return StarletteHTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"code": "not_implemented", "message": message},
    )


__all__ = [
    "AppError",
    "build_error_response",
    "http_exception_handler",
    "not_implemented_error",
    "validation_exception_handler",
]
