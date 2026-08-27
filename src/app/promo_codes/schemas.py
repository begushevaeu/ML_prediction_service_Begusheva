"""Promo code API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


def normalize_promo_code(value: str) -> str:
    """Normalize user-entered promo codes."""

    return value.strip().upper()


class PromoCodeCreate(BaseModel):
    """Admin request to create a fixed-credit promo code."""

    code: str = Field(min_length=3, max_length=64)
    credit_amount: int = Field(gt=0)
    max_redemptions: int = Field(gt=0)
    is_active: bool = True
    starts_at: datetime
    expires_at: datetime

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return normalize_promo_code(value)

    @model_validator(mode="after")
    def validate_window(self) -> "PromoCodeCreate":
        if self.starts_at >= self.expires_at:
            raise ValueError("starts_at must be before expires_at")
        return self


class PromoCodeRead(BaseModel):
    """Public admin promo code record."""

    id: int
    code: str
    credit_amount: int
    max_redemptions: int | None
    redemptions_count: int
    is_active: bool
    starts_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PromoCodeListResponse(BaseModel):
    """Paginated-style promo code list response."""

    items: list[PromoCodeRead]
    total: int


class PromoRedeemCreate(BaseModel):
    """User request to redeem a promo code."""

    code: str = Field(min_length=3, max_length=64)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return normalize_promo_code(value)


class PromoRedemptionRead(BaseModel):
    """Public promo redemption response."""

    id: int
    code: str
    credits_granted: int
    balance_after_credits: int
    created_at: datetime


class PromoRedemptionListResponse(BaseModel):
    """Paginated-style promo redemption list response."""

    items: list[PromoRedemptionRead]
    total: int


__all__ = [
    "PromoCodeCreate",
    "PromoCodeListResponse",
    "PromoCodeRead",
    "PromoRedeemCreate",
    "PromoRedemptionListResponse",
    "PromoRedemptionRead",
    "normalize_promo_code",
]
