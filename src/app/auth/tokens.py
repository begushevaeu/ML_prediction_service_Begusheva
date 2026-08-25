"""JWT token helpers."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import Settings, get_settings


class TokenError(ValueError):
    """Raised when an access token is invalid."""


def create_access_token(subject: str, settings: Settings | None = None) -> str:
    """Create a signed JWT access token."""

    resolved_settings = settings or get_settings()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=resolved_settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": issued_at,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        resolved_settings.jwt_secret_key,
        algorithm=resolved_settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Decode and validate a JWT access token."""

    resolved_settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            resolved_settings.jwt_secret_key,
            algorithms=[resolved_settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid access token") from exc

    if not payload.get("sub"):
        raise TokenError("Access token is missing subject")

    return payload


__all__ = ["TokenError", "create_access_token", "decode_access_token"]
