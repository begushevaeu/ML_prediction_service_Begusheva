"""Promo code lifecycle services."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.service import credit_user_balance
from app.db.models import BillingTransaction, PromoCode, PromoRedemption
from app.promo_codes.schemas import PromoCodeCreate, normalize_promo_code


class PromoCodeError(ValueError):
    """Base class for expected promo code errors."""


class DuplicatePromoCodeError(PromoCodeError):
    """Raised when a promo code already exists."""


class PromoCodeNotFoundError(PromoCodeError):
    """Raised when a promo code cannot be found."""


class PromoCodeNotActiveError(PromoCodeError):
    """Raised when a promo code cannot currently be redeemed."""


class PromoCodeAlreadyRedeemedError(PromoCodeError):
    """Raised when a user tries to redeem the same code twice."""


class PromoCodeLimitReachedError(PromoCodeError):
    """Raised when a promo code has no remaining redemptions."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def list_promo_codes(session: Session) -> list[PromoCode]:
    """Return all promo codes for admin review."""

    return (
        session.execute(
            select(PromoCode).order_by(PromoCode.created_at.desc(), PromoCode.id.desc())
        )
        .scalars()
        .all()
    )


def get_promo_code(
    session: Session,
    *,
    promo_code_id: int,
    lock: bool = False,
) -> PromoCode:
    """Return one promo code for admin operations."""

    statement = select(PromoCode).where(PromoCode.id == promo_code_id)
    if lock:
        statement = statement.with_for_update()

    promo_code = session.scalar(statement)
    if promo_code is None:
        raise PromoCodeNotFoundError("Promo code not found")
    return promo_code


def create_promo_code(
    session: Session,
    *,
    created_by_user_id: int,
    payload: PromoCodeCreate,
) -> PromoCode:
    """Create a fixed-credit promo code."""

    existing = session.scalar(select(PromoCode).where(PromoCode.code == payload.code))
    if existing is not None:
        raise DuplicatePromoCodeError("Promo code already exists")

    promo_code = PromoCode(
        code=payload.code,
        credit_amount=payload.credit_amount,
        max_redemptions=payload.max_redemptions,
        is_active=payload.is_active,
        starts_at=payload.starts_at,
        expires_at=payload.expires_at,
        created_by_user_id=created_by_user_id,
    )
    session.add(promo_code)
    session.flush()
    return promo_code


def deactivate_promo_code(
    session: Session,
    *,
    promo_code_id: int,
) -> PromoCode:
    """Deactivate a promo code without deleting redemption history."""

    promo_code = get_promo_code(session, promo_code_id=promo_code_id, lock=True)
    promo_code.is_active = False
    session.flush()
    return promo_code


def _validate_redeemable(promo_code: PromoCode) -> None:
    now = _utc_now()
    if not promo_code.is_active:
        raise PromoCodeNotActiveError("Promo code is not active")

    if promo_code.starts_at is not None and _as_utc(promo_code.starts_at) > now:
        raise PromoCodeNotActiveError("Promo code is not active yet")

    if promo_code.expires_at is not None and _as_utc(promo_code.expires_at) <= now:
        raise PromoCodeNotActiveError("Promo code is expired")

    if (
        promo_code.max_redemptions is not None
        and promo_code.redemptions_count >= promo_code.max_redemptions
    ):
        raise PromoCodeLimitReachedError("Promo code redemption limit reached")


def redeem_promo_code(
    session: Session,
    *,
    user_id: int,
    code: str,
) -> tuple[PromoRedemption, BillingTransaction]:
    """Redeem a promo code and credit the user's balance once."""

    normalized_code = normalize_promo_code(code)
    promo_code = session.scalar(
        select(PromoCode).where(PromoCode.code == normalized_code).with_for_update(),
    )
    if promo_code is None:
        raise PromoCodeNotFoundError("Promo code not found")

    existing_redemption = session.scalar(
        select(PromoRedemption).where(
            PromoRedemption.user_id == user_id,
            PromoRedemption.promo_code_id == promo_code.id,
        ),
    )
    if existing_redemption is not None:
        raise PromoCodeAlreadyRedeemedError("Promo code already redeemed")

    _validate_redeemable(promo_code)

    redemption = PromoRedemption(
        user_id=user_id,
        promo_code_id=promo_code.id,
        credits_granted=promo_code.credit_amount,
    )
    promo_code.redemptions_count += 1
    session.add(redemption)
    session.flush()

    transaction = credit_user_balance(
        session,
        user_id=user_id,
        amount_credits=promo_code.credit_amount,
        transaction_type="promo_credit",
        description=f"Promo code {promo_code.code}",
        idempotency_key=f"promo:{user_id}:{promo_code.id}:credit",
        promo_redemption_id=redemption.id,
    )
    session.flush()
    return redemption, transaction


def list_user_redemptions(session: Session, *, user_id: int) -> list[PromoRedemption]:
    """Return promo redemptions owned by a user."""

    return (
        session.execute(
            select(PromoRedemption)
            .where(PromoRedemption.user_id == user_id)
            .order_by(PromoRedemption.created_at.desc(), PromoRedemption.id.desc()),
        )
        .scalars()
        .all()
    )


__all__ = [
    "DuplicatePromoCodeError",
    "PromoCodeAlreadyRedeemedError",
    "PromoCodeError",
    "PromoCodeLimitReachedError",
    "PromoCodeNotActiveError",
    "PromoCodeNotFoundError",
    "create_promo_code",
    "deactivate_promo_code",
    "get_promo_code",
    "list_promo_codes",
    "list_user_redemptions",
    "redeem_promo_code",
]
