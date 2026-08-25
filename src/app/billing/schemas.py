"""Billing API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreditBalanceRead(BaseModel):
    """Current credit balance response."""

    credits_available: int
    updated_at: datetime


class BillingTransactionRead(BaseModel):
    """Public billing ledger row."""

    id: int
    user_id: int
    transaction_type: str
    direction: str
    amount_credits: int
    balance_after_credits: int
    status: str
    description: str | None
    created_at: datetime


class BillingTransactionListResponse(BaseModel):
    """Paginated-style billing ledger response."""

    items: list[BillingTransactionRead]
    total: int


class BillingAdjustmentCreate(BaseModel):
    """Admin-only manual billing adjustment request."""

    user_id: int = Field(gt=0)
    direction: Literal["credit", "debit"] = "credit"
    amount_credits: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=255)
    idempotency_key: str | None = Field(default=None, max_length=255)


__all__ = [
    "BillingAdjustmentCreate",
    "BillingTransactionListResponse",
    "BillingTransactionRead",
    "CreditBalanceRead",
]
