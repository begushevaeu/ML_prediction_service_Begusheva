"""Billing API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, DbSession, require_roles
from app.billing.schemas import (
    BillingAdjustmentCreate,
    BillingTransactionListResponse,
    BillingTransactionRead,
    CreditBalanceRead,
)
from app.billing.service import (
    BillingTargetNotFoundError,
    InsufficientCreditsError,
    credit_user_balance,
    debit_user_balance,
)
from app.db.models import BillingTransaction, CreditBalance
from app.users.service import ADMIN_ROLE

router = APIRouter(prefix="/billing", tags=["billing"])


def transaction_to_read(transaction: BillingTransaction) -> BillingTransactionRead:
    """Convert a ledger row into the public response contract."""

    return BillingTransactionRead(
        id=transaction.id,
        user_id=transaction.user_id,
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


@router.post(
    "/adjustments",
    response_model=BillingTransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create admin billing adjustment",
)
def create_adjustment(
    payload: BillingAdjustmentCreate,
    session: DbSession,
    current_user: Annotated[object, Depends(require_roles(ADMIN_ROLE))],
) -> BillingTransactionRead:
    """Credit or debit a user's balance through an admin adjustment."""

    try:
        if payload.direction == "credit":
            transaction = credit_user_balance(
                session,
                user_id=payload.user_id,
                amount_credits=payload.amount_credits,
                transaction_type="adjustment",
                description=payload.description,
                idempotency_key=payload.idempotency_key,
            )
        else:
            transaction = debit_user_balance(
                session,
                user_id=payload.user_id,
                amount_credits=payload.amount_credits,
                transaction_type="adjustment",
                description=payload.description,
                idempotency_key=payload.idempotency_key,
            )
    except BillingTargetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing target user not found",
        ) from exc
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "insufficient_credits",
                "message": str(exc),
                "details": {"available": exc.available, "required": exc.required},
            },
        ) from exc

    session.commit()
    session.refresh(transaction)
    return transaction_to_read(transaction)


__all__ = ["router"]
