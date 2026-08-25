"""Payment API endpoints."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, DbSession
from app.db.models import Payment
from app.payments.schemas import PaymentCreate, PaymentListResponse, PaymentRead
from app.payments.service import (
    PaymentNotFoundError,
    confirm_mock_payment,
    create_mock_payment,
    get_owned_payment,
)

router = APIRouter(prefix="/payments", tags=["payments"])


def payment_to_read(payment: Payment) -> PaymentRead:
    """Convert a payment row into the public response contract."""

    return PaymentRead(
        id=payment.id,
        provider=payment.provider,
        provider_payment_id=payment.provider_payment_id,
        status=payment.status,
        credits_purchased=payment.credits_purchased,
        amount_cents=payment.amount_cents,
        currency=payment.currency,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


@router.get("", response_model=PaymentListResponse, summary="List payments")
def list_payments(current_user: CurrentUser, session: DbSession) -> PaymentListResponse:
    """Return payment records for the authenticated user."""

    payments = (
        session.execute(
            select(Payment)
            .where(Payment.user_id == current_user.id)
            .order_by(Payment.created_at.desc(), Payment.id.desc()),
        )
        .scalars()
        .all()
    )
    items = [payment_to_read(payment) for payment in payments]
    return PaymentListResponse(items=items, total=len(items))


@router.get(
    "/{payment_id}",
    response_model=PaymentRead,
    summary="Get a payment",
)
def get_payment(
    payment_id: Annotated[int, Path(gt=0)],
    current_user: CurrentUser,
    session: DbSession,
) -> PaymentRead:
    """Return one owned payment record."""

    try:
        payment = get_owned_payment(
            session,
            user_id=current_user.id,
            payment_id=payment_id,
        )
    except PaymentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        ) from exc

    return payment_to_read(payment)


@router.post(
    "",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a payment",
)
def create_payment(
    payload: PaymentCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> PaymentRead:
    """Create a pending mock payment."""

    payment = create_mock_payment(
        session,
        user_id=current_user.id,
        payload=payload,
    )
    session.commit()
    session.refresh(payment)
    return payment_to_read(payment)


@router.post(
    "/{payment_id}/confirm",
    response_model=PaymentRead,
    summary="Confirm a payment",
)
def confirm_payment(
    payment_id: Annotated[int, Path(gt=0)],
    current_user: CurrentUser,
    session: DbSession,
) -> PaymentRead:
    """Confirm an owned mock payment and credit the balance once."""

    try:
        payment = confirm_mock_payment(
            session,
            user_id=current_user.id,
            payment_id=payment_id,
        )
    except PaymentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        ) from exc

    session.commit()
    session.refresh(payment)
    return payment_to_read(payment)


__all__ = ["router"]
