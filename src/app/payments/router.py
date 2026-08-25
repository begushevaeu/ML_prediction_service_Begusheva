"""Payment API endpoints."""

from fastapi import APIRouter, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, DbSession
from app.core.errors import not_implemented_error
from app.db.models import Payment
from app.payments.schemas import PaymentCreate, PaymentListResponse, PaymentRead

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


@router.post(
    "",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Create a payment",
)
def create_payment(payload: PaymentCreate, current_user: CurrentUser) -> None:
    """Validate the payment request contract before payment processing is implemented."""

    raise not_implemented_error("Payment processing is implemented in Step 10.")


__all__ = ["router"]
