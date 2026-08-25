"""User API schemas."""

from pydantic import BaseModel, Field, field_validator


def normalize_email(value: str) -> str:
    """Normalize and minimally validate an email address."""

    email = value.strip().lower()
    if "@" not in email or "." not in email.rsplit("@", maxsplit=1)[-1]:
        raise ValueError("Invalid email address")
    return email


class UserCreate(BaseModel):
    """Registration request payload."""

    email: str = Field(max_length=320)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class UserUpdate(BaseModel):
    """Allowed current-user profile updates."""

    full_name: str | None = Field(default=None, max_length=200)


class UserRead(BaseModel):
    """Public user representation."""

    id: int
    email: str
    full_name: str | None
    role: str
    is_active: bool


class AdminCheckResponse(BaseModel):
    """Admin-only authorization check response."""

    status: str
    role: str


__all__ = ["AdminCheckResponse", "UserCreate", "UserRead", "UserUpdate", "normalize_email"]
