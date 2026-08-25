"""Billing API endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, DbSession
from app.billing.schemas import (
    BillingTransactionListResponse,
    BillingTransactionRead,
    CreditBalanceRead,
)
from app.db.models import BillingTransaction, CreditBalance

router = APIRouter(prefix="/billing", tags=["billing"])


def transaction_to_read(transaction: BillingTransaction) -> BillingTransactionRead:
    """Convert a ledger row into the public response contract."""

    return BillingTransactionRead(
        id=transaction.id,
        transaction_type=transaction.transaction_type,
        direction=transaction.direction,
        amount_credits=transaction.amount_credits,
        balance_after_credits=transaction.balance_after_credits,
        status=transaction.status,
        description=transaction.description,
        created_at=transaction.created_at,
    )


@router.get("/balance", response_model=CreditBalanceRead, summary="Get current credit balance")
def get_balance(current_user: CurrentUser, session: DbSession) -> CreditBalanceRead:
    """Return the authenticated user's credit balance."""

    balance = session.scalar(
        select(CreditBalance).where(CreditBalance.user_id == current_user.id),
    )
    if balance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit balance not found",
        )

    return CreditBalanceRead(
        credits_available=balance.credits_available,
        updated_at=balance.updated_at,
    )


@router.get(
    "/transactions",
    response_model=BillingTransactionListResponse,
    summary="List billing transactions",
)
def list_transactions(
    current_user: CurrentUser,
    session: DbSession,
) -> BillingTransactionListResponse:
    """Return billing ledger rows for the authenticated user."""

    transactions = (
        session.execute(
            select(BillingTransaction)
            .where(BillingTransaction.user_id == current_user.id)
            .order_by(BillingTransaction.created_at.desc(), BillingTransaction.id.desc()),
        )
        .scalars()
        .all()
    )
    items = [transaction_to_read(transaction) for transaction in transactions]
    return BillingTransactionListResponse(items=items, total=len(items))


__all__ = ["router"]
