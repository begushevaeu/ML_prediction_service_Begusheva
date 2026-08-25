"""Billing balance and ledger services."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BillingTransaction, CreditBalance, User


class BillingError(ValueError):
    """Base class for expected billing errors."""


class BillingTargetNotFoundError(BillingError):
    """Raised when a billing target user or balance does not exist."""


class InsufficientCreditsError(BillingError):
    """Raised when a balance cannot cover a debit."""

    def __init__(self, *, available: int, required: int) -> None:
        super().__init__(f"Insufficient credits: {available} available, {required} required")
        self.available = available
        self.required = required


def _get_existing_transaction(
    session: Session,
    idempotency_key: str | None,
) -> BillingTransaction | None:
    if not idempotency_key:
        return None

    return session.scalar(
        select(BillingTransaction).where(BillingTransaction.idempotency_key == idempotency_key),
    )


def get_credit_balance(session: Session, user_id: int, *, lock: bool = False) -> CreditBalance:
    """Return a user's credit balance."""

    statement = select(CreditBalance).where(CreditBalance.user_id == user_id)
    if lock:
        statement = statement.with_for_update()

    balance = session.scalar(statement)
    if balance is None:
        user = session.get(User, user_id)
        if user is None:
            raise BillingTargetNotFoundError("Billing target user not found")
        balance = CreditBalance(user_id=user_id, credits_available=0)
        session.add(balance)
        session.flush()

    return balance


def require_sufficient_credits(
    session: Session,
    user_id: int,
    amount_credits: int,
) -> CreditBalance:
    """Ensure a balance can cover a future debit."""

    balance = get_credit_balance(session, user_id)
    if balance.credits_available < amount_credits:
        raise InsufficientCreditsError(
            available=balance.credits_available,
            required=amount_credits,
        )

    return balance


def credit_user_balance(
    session: Session,
    *,
    user_id: int,
    amount_credits: int,
    transaction_type: str,
    description: str | None = None,
    idempotency_key: str | None = None,
    payment_id: int | None = None,
    promo_redemption_id: int | None = None,
) -> BillingTransaction:
    """Credit a user's balance and write one ledger transaction."""

    existing = _get_existing_transaction(session, idempotency_key)
    if existing is not None:
        return existing

    balance = get_credit_balance(session, user_id, lock=True)
    balance.credits_available += amount_credits
    transaction = BillingTransaction(
        user_id=user_id,
        balance_id=balance.id,
        payment_id=payment_id,
        promo_redemption_id=promo_redemption_id,
        transaction_type=transaction_type,
        direction="credit",
        amount_credits=amount_credits,
        balance_after_credits=balance.credits_available,
        status="posted",
        description=description,
        idempotency_key=idempotency_key,
    )
    session.add(transaction)
    session.flush()
    return transaction


def debit_user_balance(
    session: Session,
    *,
    user_id: int,
    amount_credits: int,
    transaction_type: str,
    description: str | None = None,
    idempotency_key: str | None = None,
    prediction_task_id: int | None = None,
) -> BillingTransaction:
    """Debit a user's balance and write one ledger transaction."""

    existing = _get_existing_transaction(session, idempotency_key)
    if existing is not None:
        return existing

    balance = get_credit_balance(session, user_id, lock=True)
    if balance.credits_available < amount_credits:
        raise InsufficientCreditsError(
            available=balance.credits_available,
            required=amount_credits,
        )

    balance.credits_available -= amount_credits
    transaction = BillingTransaction(
        user_id=user_id,
        balance_id=balance.id,
        prediction_task_id=prediction_task_id,
        transaction_type=transaction_type,
        direction="debit",
        amount_credits=amount_credits,
        balance_after_credits=balance.credits_available,
        status="posted",
        description=description,
        idempotency_key=idempotency_key,
    )
    session.add(transaction)
    session.flush()
    return transaction


def debit_prediction_success(
    session: Session,
    *,
    user_id: int,
    prediction_task_id: int,
    amount_credits: int,
) -> BillingTransaction:
    """Debit credits after a successful prediction."""

    return debit_user_balance(
        session,
        user_id=user_id,
        amount_credits=amount_credits,
        transaction_type="prediction_debit",
        description=f"Prediction task #{prediction_task_id}",
        idempotency_key=f"prediction:{prediction_task_id}:debit",
        prediction_task_id=prediction_task_id,
    )


__all__ = [
    "BillingError",
    "BillingTargetNotFoundError",
    "InsufficientCreditsError",
    "credit_user_balance",
    "debit_prediction_success",
    "debit_user_balance",
    "get_credit_balance",
    "require_sufficient_credits",
]
