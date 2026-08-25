"""Payment API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PaymentCreate(BaseModel):
    """Contract for a future payment request."""

    credits_purchased: int = Field(gt=0)
    amount_cents: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class PaymentRead(BaseModel):
    """Public payment record."""

    id: int
    provider: str
    provider_payment_id: str | None
    status: str
    credits_purchased: int
    amount_cents: int
    currency: str
    created_at: datetime
    updated_at: datetime


class PaymentListResponse(BaseModel):
    """Paginated-style payment list response."""

    items: list[PaymentRead]
    total: int


__all__ = ["PaymentCreate", "PaymentListResponse", "PaymentRead"]
