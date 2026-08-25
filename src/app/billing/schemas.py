"""Billing API schemas."""

from datetime import datetime

from pydantic import BaseModel


class CreditBalanceRead(BaseModel):
    """Current credit balance response."""

    credits_available: int
    updated_at: datetime


class BillingTransactionRead(BaseModel):
    """Public billing ledger row."""

    id: int
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


__all__ = [
    "BillingTransactionListResponse",
    "BillingTransactionRead",
    "CreditBalanceRead",
]
