"""Authentication response schemas."""

from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Bearer token response."""

    access_token: str
    token_type: str = "bearer"


__all__ = ["TokenResponse"]
