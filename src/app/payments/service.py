"""Payment lifecycle services."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.service import credit_user_balance
from app.db.models import Payment
from app.payments.schemas import PaymentCreate


class PaymentError(ValueError):
    """Base class for expected payment errors."""


class PaymentNotFoundError(PaymentError):
    """Raised when an owned payment cannot be found."""


def get_owned_payment(
    session: Session,
    *,
    user_id: int,
    payment_id: int,
    lock: bool = False,
) -> Payment:
    """Return a payment owned by the user."""

    statement = select(Payment).where(Payment.id == payment_id, Payment.user_id == user_id)
    if lock:
        statement = statement.with_for_update()

    payment = session.scalar(statement)
    if payment is None:
        raise PaymentNotFoundError("Payment not found")

    return payment


def create_mock_payment(
    session: Session,
    *,
    user_id: int,
    payload: PaymentCreate,
) -> Payment:
    """Create a pending mock payment."""

    payment = Payment(
        user_id=user_id,
        provider="mock",
        provider_payment_id=f"mock_{uuid4().hex}",
        status="pending",
        credits_purchased=payload.credits_purchased,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
    )
    session.add(payment)
    session.flush()
    return payment


def confirm_mock_payment(
    session: Session,
    *,
    user_id: int,
    payment_id: int,
) -> Payment:
    """Confirm a mock payment and credit the user's balance once."""

    payment = get_owned_payment(
        session,
        user_id=user_id,
        payment_id=payment_id,
        lock=True,
    )
    if payment.status == "succeeded":
        return payment

    payment.status = "succeeded"
    credit_user_balance(
        session,
        user_id=user_id,
        amount_credits=payment.credits_purchased,
        transaction_type="payment_credit",
        description=f"Mock payment #{payment.id}",
        idempotency_key=f"payment:{payment.id}:credit",
        payment_id=payment.id,
    )
    session.flush()
    return payment


__all__ = [
    "PaymentError",
    "PaymentNotFoundError",
    "confirm_mock_payment",
    "create_mock_payment",
    "get_owned_payment",
]
