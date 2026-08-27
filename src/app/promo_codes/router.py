"""Promo code API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.auth.dependencies import CurrentUser, DbSession, require_roles
from app.db.models import BillingTransaction, PromoCode, PromoRedemption, User
from app.promo_codes.schemas import (
    PromoCodeCreate,
    PromoCodeListResponse,
    PromoCodeRead,
    PromoRedeemCreate,
    PromoRedemptionListResponse,
    PromoRedemptionRead,
)
from app.promo_codes.service import (
    DuplicatePromoCodeError,
    PromoCodeAlreadyRedeemedError,
    PromoCodeLimitReachedError,
    PromoCodeNotActiveError,
    PromoCodeNotFoundError,
    create_promo_code,
    deactivate_promo_code,
    list_promo_codes,
    list_user_redemptions,
    redeem_promo_code,
)
from app.users.service import ADMIN_ROLE

router = APIRouter(prefix="/promo-codes", tags=["promo-codes"])
AdminUser = Annotated[User, Depends(require_roles(ADMIN_ROLE))]


def promo_code_to_read(promo_code: PromoCode) -> PromoCodeRead:
    """Convert a promo code row into the public response contract."""

    return PromoCodeRead(
        id=promo_code.id,
        code=promo_code.code,
        credit_amount=promo_code.credit_amount,
        max_redemptions=promo_code.max_redemptions,
        redemptions_count=promo_code.redemptions_count,
        is_active=promo_code.is_active,
        starts_at=promo_code.starts_at,
        expires_at=promo_code.expires_at,
        created_at=promo_code.created_at,
        updated_at=promo_code.updated_at,
    )


def redemption_to_read(
    redemption: PromoRedemption,
    *,
    transaction: BillingTransaction | None = None,
) -> PromoRedemptionRead:
    """Convert a promo redemption row into the public response contract."""

    balance_after_credits = (
        transaction.balance_after_credits if transaction is not None else redemption.credits_granted
    )
    return PromoRedemptionRead(
        id=redemption.id,
        code=redemption.promo_code.code,
        credits_granted=redemption.credits_granted,
        balance_after_credits=balance_after_credits,
        created_at=redemption.created_at,
    )


@router.get(
    "",
    response_model=PromoCodeListResponse,
    summary="List promo codes",
)
def list_codes(
    session: DbSession,
    admin_user: AdminUser,
) -> PromoCodeListResponse:
    """Return all promo codes for admins."""

    promo_codes = list_promo_codes(session)
    items = [promo_code_to_read(promo_code) for promo_code in promo_codes]
    return PromoCodeListResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=PromoCodeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a promo code",
)
def create_code(
    payload: PromoCodeCreate,
    session: DbSession,
    admin_user: AdminUser,
) -> PromoCodeRead:
    """Create a fixed-credit promo code."""

    try:
        promo_code = create_promo_code(
            session,
            created_by_user_id=admin_user.id,
            payload=payload,
        )
    except DuplicatePromoCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "promo_code_exists", "message": str(exc)},
        ) from exc

    session.commit()
    session.refresh(promo_code)
    return promo_code_to_read(promo_code)


@router.patch(
    "/{promo_code_id}/deactivate",
    response_model=PromoCodeRead,
    summary="Deactivate a promo code",
)
def deactivate_code(
    promo_code_id: Annotated[int, Path(gt=0)],
    session: DbSession,
    admin_user: AdminUser,
) -> PromoCodeRead:
    """Deactivate a promo code while preserving redemption history."""

    try:
        promo_code = deactivate_promo_code(session, promo_code_id=promo_code_id)
    except PromoCodeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promo code not found",
        ) from exc

    session.commit()
    session.refresh(promo_code)
    return promo_code_to_read(promo_code)


@router.get(
    "/redemptions",
    response_model=PromoRedemptionListResponse,
    summary="List promo redemptions",
)
def list_redemptions(
    current_user: CurrentUser,
    session: DbSession,
) -> PromoRedemptionListResponse:
    """Return promo redemptions owned by the authenticated user."""

    redemptions = list_user_redemptions(session, user_id=current_user.id)
    items = [redemption_to_read(redemption) for redemption in redemptions]
    return PromoRedemptionListResponse(items=items, total=len(items))


@router.post(
    "/redeem",
    response_model=PromoRedemptionRead,
    summary="Redeem a promo code",
)
def redeem_code(
    payload: PromoRedeemCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> PromoRedemptionRead:
    """Redeem a promo code into the user's credit balance."""

    try:
        redemption, transaction = redeem_promo_code(
            session,
            user_id=current_user.id,
            code=payload.code,
        )
    except PromoCodeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promo code not found",
        ) from exc
    except PromoCodeNotActiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "promo_not_active", "message": str(exc)},
        ) from exc
    except PromoCodeAlreadyRedeemedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "promo_already_redeemed", "message": str(exc)},
        ) from exc
    except PromoCodeLimitReachedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "promo_limit_reached", "message": str(exc)},
        ) from exc

    session.commit()
    session.refresh(redemption)
    return redemption_to_read(redemption, transaction=transaction)


__all__ = ["router"]
