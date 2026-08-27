"""Admin API endpoints."""

from __future__ import annotations

import os
import shutil
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Path as ApiPath
from redis import Redis
from sqlalchemy import func, select, text
from sqlalchemy.orm import selectinload

from app.admin.schemas import (
    AdminActivityPointRead,
    AdminActivityResponse,
    AdminBillingTransactionListResponse,
    AdminBillingTransactionRead,
    AdminDashboardSummaryRead,
    AdminEventListResponse,
    AdminEventRead,
    AdminLogListResponse,
    AdminLogRead,
    AdminModelListResponse,
    AdminModelRead,
    AdminMonitoringSummaryRead,
    AdminPaymentListResponse,
    AdminPaymentRead,
    AdminPredictionListResponse,
    AdminPredictionRead,
    AdminPromoRedemptionListResponse,
    AdminPromoRedemptionRead,
    AdminServiceStatusRead,
    AdminSystemSettingsRead,
    AdminSystemUsageRead,
    AdminUserDetailRead,
    AdminUserListResponse,
    AdminUserRead,
    AdminUserStatusUpdate,
)
from app.auth.dependencies import DbSession, require_roles
from app.core.config import Settings, get_settings
from app.db.models import (
    BillingTransaction,
    MLModel,
    Payment,
    PredictionTask,
    PromoCode,
    PromoRedemption,
    User,
)
from app.users.service import ADMIN_ROLE

router = APIRouter(prefix="/admin", tags=["admin"])
AdminUser = Annotated[User, Depends(require_roles(ADMIN_ROLE))]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _sum_int(value: object) -> int:
    return int(value or 0)


def _user_to_admin_read(user: User) -> AdminUserRead:
    balance = user.credit_balance
    role = user.role.name if user.role is not None else "-"
    return AdminUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=role,
        is_active=user.is_active,
        credits_available=balance.credits_available if balance is not None else 0,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _model_to_admin_read(model: MLModel, runs_count: int) -> AdminModelRead:
    owner = model.owner
    return AdminModelRead(
        id=model.id,
        name=model.name,
        owner_id=model.owner_id,
        owner_email=owner.email if owner is not None else "-",
        framework=model.framework,
        status=model.status,
        runs_count=runs_count,
        metadata=model.model_metadata,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _prediction_costs_by_id(
    session: DbSession,
    prediction_ids: Iterable[int],
) -> dict[int, int]:
    ids = list(prediction_ids)
    if not ids:
        return {}

    rows = session.execute(
        select(
            BillingTransaction.prediction_task_id,
            func.coalesce(func.sum(BillingTransaction.amount_credits), 0),
        )
        .where(
            BillingTransaction.prediction_task_id.in_(ids),
            BillingTransaction.transaction_type == "prediction_debit",
            BillingTransaction.status == "posted",
        )
        .group_by(BillingTransaction.prediction_task_id),
    ).all()
    return {int(prediction_id): int(amount) for prediction_id, amount in rows if prediction_id}


def _prediction_to_admin_read(
    prediction: PredictionTask,
    *,
    cost_credits: int,
) -> AdminPredictionRead:
    user = prediction.user
    model = prediction.model
    return AdminPredictionRead(
        id=prediction.id,
        user_id=prediction.user_id,
        user_email=user.email if user is not None else "-",
        model_id=prediction.model_id,
        model_name=model.name if model is not None else f"Model #{prediction.model_id}",
        status=prediction.status,
        cost_credits=cost_credits,
        result_payload=prediction.result_payload,
        error_message=prediction.error_message,
        started_at=prediction.started_at,
        completed_at=prediction.completed_at,
        created_at=prediction.created_at,
        updated_at=prediction.updated_at,
    )


def _payment_to_admin_read(payment: Payment) -> AdminPaymentRead:
    user = payment.user
    return AdminPaymentRead(
        id=payment.id,
        user_id=payment.user_id,
        user_email=user.email if user is not None else "-",
        provider=payment.provider,
        provider_payment_id=payment.provider_payment_id,
        status=payment.status,
        credits_purchased=payment.credits_purchased,
        amount_cents=payment.amount_cents,
        currency=payment.currency,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


def _transaction_to_admin_read(
    transaction: BillingTransaction,
) -> AdminBillingTransactionRead:
    user = transaction.user
    return AdminBillingTransactionRead(
        id=transaction.id,
        user_id=transaction.user_id,
        user_email=user.email if user is not None else "-",
        transaction_type=transaction.transaction_type,
        direction=transaction.direction,
        amount_credits=transaction.amount_credits,
        balance_after_credits=transaction.balance_after_credits,
        status=transaction.status,
        description=transaction.description,
        prediction_task_id=transaction.prediction_task_id,
        payment_id=transaction.payment_id,
        promo_redemption_id=transaction.promo_redemption_id,
        created_at=transaction.created_at,
    )


def _bucket_predictions(
    predictions: Iterable[PredictionTask],
) -> list[AdminActivityPointRead]:
    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "succeeded": 0, "failed": 0},
    )
    for prediction in predictions:
        bucket_key = _as_utc(prediction.created_at).date().isoformat()
        bucket = buckets[bucket_key]
        bucket["total"] += 1
        if prediction.status == "succeeded":
            bucket["succeeded"] += 1
        elif prediction.status == "failed":
            bucket["failed"] += 1

    return [
        AdminActivityPointRead(
            date=date_label,
            predictions_total=values["total"],
            predictions_succeeded=values["succeeded"],
            predictions_failed=values["failed"],
        )
        for date_label, values in sorted(buckets.items())
    ]


def _event_sort_key(event: AdminEventRead) -> datetime:
    return _as_utc(event.created_at)


def _check_redis(settings: Settings) -> AdminServiceStatusRead:
    try:
        client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=0.4,
            socket_timeout=0.4,
        )
        client.ping()
    except Exception as exc:  # noqa: BLE001
        return AdminServiceStatusRead(name="Redis", status="unknown", details=str(exc))
    return AdminServiceStatusRead(name="Redis", status="ok")


@router.get(
    "/dashboard/summary",
    response_model=AdminDashboardSummaryRead,
    summary="Get admin dashboard summary",
)
def get_dashboard_summary(
    session: DbSession,
    admin_user: AdminUser,
) -> AdminDashboardSummaryRead:
    """Return global platform KPI values for admins."""

    users_total = _sum_int(session.scalar(select(func.count(User.id))))
    users_active = _sum_int(
        session.scalar(select(func.count(User.id)).where(User.is_active.is_(True))),
    )
    models_total = _sum_int(session.scalar(select(func.count(MLModel.id))))
    predictions_total = _sum_int(session.scalar(select(func.count(PredictionTask.id))))
    predictions_succeeded = _sum_int(
        session.scalar(
            select(func.count(PredictionTask.id)).where(PredictionTask.status == "succeeded"),
        ),
    )
    predictions_failed = _sum_int(
        session.scalar(
            select(func.count(PredictionTask.id)).where(PredictionTask.status == "failed"),
        ),
    )
    credits_debited = _sum_int(
        session.scalar(
            select(func.coalesce(func.sum(BillingTransaction.amount_credits), 0)).where(
                BillingTransaction.direction == "debit",
                BillingTransaction.status == "posted",
            ),
        ),
    )
    credits_credited = _sum_int(
        session.scalar(
            select(func.coalesce(func.sum(BillingTransaction.amount_credits), 0)).where(
                BillingTransaction.direction == "credit",
                BillingTransaction.status == "posted",
            ),
        ),
    )
    credits_purchased = _sum_int(
        session.scalar(
            select(func.coalesce(func.sum(Payment.credits_purchased), 0)).where(
                Payment.status == "succeeded",
            ),
        ),
    )
    payments_total = _sum_int(session.scalar(select(func.count(Payment.id))))
    payments_succeeded = _sum_int(
        session.scalar(select(func.count(Payment.id)).where(Payment.status == "succeeded")),
    )
    promo_codes_total = _sum_int(session.scalar(select(func.count(PromoCode.id))))
    promo_redemptions_total = _sum_int(session.scalar(select(func.count(PromoRedemption.id))))
    success_rate = (
        round((predictions_succeeded / predictions_total) * 100, 2) if predictions_total else 0.0
    )

    return AdminDashboardSummaryRead(
        users_total=users_total,
        users_active=users_active,
        models_total=models_total,
        predictions_total=predictions_total,
        predictions_succeeded=predictions_succeeded,
        predictions_failed=predictions_failed,
        prediction_success_rate=success_rate,
        credits_debited=credits_debited,
        credits_credited=credits_credited,
        credits_purchased=credits_purchased,
        payments_total=payments_total,
        payments_succeeded=payments_succeeded,
        promo_codes_total=promo_codes_total,
        promo_redemptions_total=promo_redemptions_total,
    )


@router.get(
    "/dashboard/activity",
    response_model=AdminActivityResponse,
    summary="Get prediction activity",
)
def get_dashboard_activity(
    session: DbSession,
    admin_user: AdminUser,
    period: Annotated[Literal["day", "week", "month"], Query()] = "week",
) -> AdminActivityResponse:
    """Return prediction counts grouped by date for a recent period."""

    days_by_period = {"day": 1, "week": 7, "month": 30}
    started_at = _utc_now() - timedelta(days=days_by_period[period])
    predictions = (
        session.execute(
            select(PredictionTask)
            .where(PredictionTask.created_at >= started_at)
            .order_by(PredictionTask.created_at.asc(), PredictionTask.id.asc()),
        )
        .scalars()
        .all()
    )
    return AdminActivityResponse(period=period, items=_bucket_predictions(predictions))


@router.get(
    "/events",
    response_model=AdminEventListResponse,
    summary="Get derived admin event feed",
)
def list_events(
    session: DbSession,
    admin_user: AdminUser,
    limit: Annotated[int, Query(gt=0, le=100)] = 20,
) -> AdminEventListResponse:
    """Return a derived event feed from current domain tables."""

    users = session.scalars(select(User).order_by(User.created_at.desc()).limit(limit)).all()
    predictions = (
        session.execute(
            select(PredictionTask)
            .options(selectinload(PredictionTask.user), selectinload(PredictionTask.model))
            .order_by(PredictionTask.updated_at.desc(), PredictionTask.id.desc())
            .limit(limit),
        )
        .scalars()
        .all()
    )
    payments = (
        session.execute(
            select(Payment)
            .options(selectinload(Payment.user))
            .order_by(Payment.updated_at.desc(), Payment.id.desc())
            .limit(limit),
        )
        .scalars()
        .all()
    )
    redemptions = (
        session.execute(
            select(PromoRedemption)
            .options(selectinload(PromoRedemption.user), selectinload(PromoRedemption.promo_code))
            .order_by(PromoRedemption.created_at.desc(), PromoRedemption.id.desc())
            .limit(limit),
        )
        .scalars()
        .all()
    )

    events: list[AdminEventRead] = []
    events.extend(
        AdminEventRead(
            created_at=user.created_at,
            event_type="user_registered",
            message="Новый пользователь зарегистрирован",
            severity="info",
            user_id=user.id,
            user_email=user.email,
            related_object=f"user:{user.id}",
        )
        for user in users
    )
    for prediction in predictions:
        severity = "error" if prediction.status == "failed" else "info"
        message = "Prediction завершен"
        if prediction.status in {"queued", "running"}:
            message = "Prediction в обработке"
        elif prediction.status == "failed":
            message = "Ошибка prediction"
        events.append(
            AdminEventRead(
                created_at=prediction.updated_at,
                event_type=f"prediction_{prediction.status}",
                message=message,
                severity=severity,
                user_id=prediction.user_id,
                user_email=prediction.user.email if prediction.user is not None else None,
                related_object=f"prediction:{prediction.id}",
            ),
        )
    events.extend(
        AdminEventRead(
            created_at=payment.updated_at,
            event_type=f"payment_{payment.status}",
            message="Баланс пополнен" if payment.status == "succeeded" else "Платеж создан",
            severity="info" if payment.status != "failed" else "error",
            user_id=payment.user_id,
            user_email=payment.user.email if payment.user is not None else None,
            related_object=f"payment:{payment.id}",
        )
        for payment in payments
    )
    events.extend(
        AdminEventRead(
            created_at=redemption.created_at,
            event_type="promo_redeemed",
            message="Промокод активирован",
            severity="info",
            user_id=redemption.user_id,
            user_email=redemption.user.email if redemption.user is not None else None,
            related_object=f"promo_redemption:{redemption.id}",
        )
        for redemption in redemptions
    )

    events = sorted(events, key=_event_sort_key, reverse=True)[:limit]
    return AdminEventListResponse(items=events, total=len(events))


@router.get("/users", response_model=AdminUserListResponse, summary="List all users")
def list_users(session: DbSession, admin_user: AdminUser) -> AdminUserListResponse:
    """Return all users with role and balance data."""

    users = (
        session.execute(
            select(User)
            .options(selectinload(User.role), selectinload(User.credit_balance))
            .order_by(User.created_at.desc(), User.id.desc()),
        )
        .scalars()
        .all()
    )
    items = [_user_to_admin_read(user) for user in users]
    return AdminUserListResponse(items=items, total=len(items))


@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetailRead,
    summary="Get admin user detail",
)
def get_user_detail(
    user_id: Annotated[int, ApiPath(gt=0)],
    session: DbSession,
    admin_user: AdminUser,
) -> AdminUserDetailRead:
    """Return one user with aggregate counts."""

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    base = _user_to_admin_read(user).model_dump()
    return AdminUserDetailRead(
        **base,
        models_total=_sum_int(
            session.scalar(select(func.count(MLModel.id)).where(MLModel.owner_id == user_id)),
        ),
        predictions_total=_sum_int(
            session.scalar(
                select(func.count(PredictionTask.id)).where(PredictionTask.user_id == user_id),
            ),
        ),
        payments_total=_sum_int(
            session.scalar(select(func.count(Payment.id)).where(Payment.user_id == user_id)),
        ),
        transactions_total=_sum_int(
            session.scalar(
                select(func.count(BillingTransaction.id)).where(
                    BillingTransaction.user_id == user_id,
                ),
            ),
        ),
    )


@router.patch(
    "/users/{user_id}/status",
    response_model=AdminUserRead,
    summary="Update user active status",
)
def update_user_status(
    user_id: Annotated[int, ApiPath(gt=0)],
    payload: AdminUserStatusUpdate,
    session: DbSession,
    admin_user: AdminUser,
) -> AdminUserRead:
    """Activate or deactivate a user account."""

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin_user.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admin cannot deactivate their own account",
        )

    user.is_active = payload.is_active
    session.commit()
    session.refresh(user)
    return _user_to_admin_read(user)


@router.get("/models", response_model=AdminModelListResponse, summary="List all models")
def list_models(session: DbSession, admin_user: AdminUser) -> AdminModelListResponse:
    """Return all model metadata across users."""

    run_counts = dict(
        session.execute(
            select(PredictionTask.model_id, func.count(PredictionTask.id)).group_by(
                PredictionTask.model_id,
            ),
        ).all(),
    )
    models = (
        session.execute(
            select(MLModel)
            .options(selectinload(MLModel.owner))
            .order_by(MLModel.created_at.desc(), MLModel.id.desc()),
        )
        .scalars()
        .all()
    )
    items = [_model_to_admin_read(model, int(run_counts.get(model.id, 0))) for model in models]
    return AdminModelListResponse(items=items, total=len(items))


@router.get(
    "/models/{model_id}",
    response_model=AdminModelRead,
    summary="Get admin model detail",
)
def get_model_detail(
    model_id: Annotated[int, ApiPath(gt=0)],
    session: DbSession,
    admin_user: AdminUser,
) -> AdminModelRead:
    """Return one model across users."""

    model = session.get(MLModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    runs_count = _sum_int(
        session.scalar(
            select(func.count(PredictionTask.id)).where(PredictionTask.model_id == model_id),
        ),
    )
    return _model_to_admin_read(model, runs_count)


@router.delete(
    "/models/{model_id}",
    response_model=AdminModelRead,
    summary="Soft-delete a model",
)
def delete_model(
    model_id: Annotated[int, ApiPath(gt=0)],
    session: DbSession,
    admin_user: AdminUser,
) -> AdminModelRead:
    """Mark a model as deleted and remove the artifact file when possible."""

    model = session.get(MLModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    runs_count = _sum_int(
        session.scalar(
            select(func.count(PredictionTask.id)).where(PredictionTask.model_id == model_id),
        ),
    )
    model.status = "deleted"
    try:
        Path(model.storage_path).unlink(missing_ok=True)
    except OSError:
        pass

    session.commit()
    session.refresh(model)
    return _model_to_admin_read(model, runs_count)


@router.get(
    "/predictions",
    response_model=AdminPredictionListResponse,
    summary="List all predictions",
)
def list_predictions(
    session: DbSession,
    admin_user: AdminUser,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> AdminPredictionListResponse:
    """Return all prediction tasks across users."""

    statement = (
        select(PredictionTask)
        .options(selectinload(PredictionTask.user), selectinload(PredictionTask.model))
        .order_by(PredictionTask.created_at.desc(), PredictionTask.id.desc())
    )
    if status_filter:
        statement = statement.where(PredictionTask.status == status_filter)

    predictions = session.execute(statement).scalars().all()
    costs = _prediction_costs_by_id(session, [prediction.id for prediction in predictions])
    items = [
        _prediction_to_admin_read(
            prediction,
            cost_credits=costs.get(prediction.id, 0),
        )
        for prediction in predictions
    ]
    return AdminPredictionListResponse(items=items, total=len(items))


@router.get(
    "/predictions/{prediction_id}",
    response_model=AdminPredictionRead,
    summary="Get admin prediction detail",
)
def get_prediction_detail(
    prediction_id: Annotated[int, ApiPath(gt=0)],
    session: DbSession,
    admin_user: AdminUser,
) -> AdminPredictionRead:
    """Return one prediction task across users."""

    prediction = session.get(PredictionTask, prediction_id)
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")
    costs = _prediction_costs_by_id(session, [prediction_id])
    return _prediction_to_admin_read(prediction, cost_credits=costs.get(prediction_id, 0))


@router.get("/payments", response_model=AdminPaymentListResponse, summary="List all payments")
def list_payments(session: DbSession, admin_user: AdminUser) -> AdminPaymentListResponse:
    """Return all payment records across users."""

    payments = (
        session.execute(
            select(Payment)
            .options(selectinload(Payment.user))
            .order_by(Payment.created_at.desc(), Payment.id.desc()),
        )
        .scalars()
        .all()
    )
    items = [_payment_to_admin_read(payment) for payment in payments]
    return AdminPaymentListResponse(items=items, total=len(items))


@router.get(
    "/payments/{payment_id}",
    response_model=AdminPaymentRead,
    summary="Get admin payment detail",
)
def get_payment_detail(
    payment_id: Annotated[int, ApiPath(gt=0)],
    session: DbSession,
    admin_user: AdminUser,
) -> AdminPaymentRead:
    """Return one payment record across users."""

    payment = session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return _payment_to_admin_read(payment)


@router.get(
    "/billing/transactions",
    response_model=AdminBillingTransactionListResponse,
    summary="List all billing transactions",
)
def list_billing_transactions(
    session: DbSession,
    admin_user: AdminUser,
) -> AdminBillingTransactionListResponse:
    """Return all credit ledger rows across users."""

    transactions = (
        session.execute(
            select(BillingTransaction)
            .options(selectinload(BillingTransaction.user))
            .order_by(BillingTransaction.created_at.desc(), BillingTransaction.id.desc()),
        )
        .scalars()
        .all()
    )
    items = [_transaction_to_admin_read(transaction) for transaction in transactions]
    return AdminBillingTransactionListResponse(items=items, total=len(items))


@router.get(
    "/promo-codes/{promo_code_id}/redemptions",
    response_model=AdminPromoRedemptionListResponse,
    summary="List promo code redemptions",
)
def list_promo_code_redemptions(
    promo_code_id: Annotated[int, ApiPath(gt=0)],
    session: DbSession,
    admin_user: AdminUser,
) -> AdminPromoRedemptionListResponse:
    """Return all redemptions for one promo code."""

    promo_code = session.get(PromoCode, promo_code_id)
    if promo_code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promo code not found")
    redemptions = (
        session.execute(
            select(PromoRedemption)
            .where(PromoRedemption.promo_code_id == promo_code_id)
            .options(selectinload(PromoRedemption.user), selectinload(PromoRedemption.promo_code))
            .order_by(PromoRedemption.created_at.desc(), PromoRedemption.id.desc()),
        )
        .scalars()
        .all()
    )
    items = [
        AdminPromoRedemptionRead(
            id=redemption.id,
            promo_code_id=redemption.promo_code_id,
            code=redemption.promo_code.code,
            user_id=redemption.user_id,
            user_email=redemption.user.email if redemption.user is not None else "-",
            credits_granted=redemption.credits_granted,
            created_at=redemption.created_at,
        )
        for redemption in redemptions
    ]
    return AdminPromoRedemptionListResponse(items=items, total=len(items))


@router.get(
    "/system/settings",
    response_model=AdminSystemSettingsRead,
    summary="Get safe system settings",
)
def get_system_settings(
    settings: Annotated[Settings, Depends(get_settings)],
    admin_user: AdminUser,
) -> AdminSystemSettingsRead:
    """Return non-secret runtime settings."""

    return AdminSystemSettingsRead(
        app_name=settings.app_name,
        app_env=settings.app_env,
        api_v1_prefix=settings.api_v1_prefix,
        prediction_price_credits=settings.prediction_price_credits,
        max_model_upload_size_bytes=settings.max_model_upload_size_bytes,
        access_token_expire_minutes=settings.access_token_expire_minutes,
        bootstrap_local_admin=settings.bootstrap_local_admin,
    )


@router.get(
    "/monitoring/summary",
    response_model=AdminMonitoringSummaryRead,
    summary="Get admin monitoring summary",
)
def get_monitoring_summary(
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
    admin_user: AdminUser,
) -> AdminMonitoringSummaryRead:
    """Return a compact monitoring summary without replacing Grafana."""

    services = [AdminServiceStatusRead(name="API", status="ok")]
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        services.append(AdminServiceStatusRead(name="PostgreSQL", status="error", details=str(exc)))
    else:
        services.append(AdminServiceStatusRead(name="PostgreSQL", status="ok"))
    services.append(_check_redis(settings))
    services.append(
        AdminServiceStatusRead(
            name="Celery",
            status="external",
            details="Worker status is tracked through prediction queues and Grafana metrics.",
        ),
    )

    disk = shutil.disk_usage("/")
    disk_percent = round((disk.used / disk.total) * 100, 2) if disk.total else None
    return AdminMonitoringSummaryRead(
        system_usage=AdminSystemUsageRead(disk_percent=disk_percent),
        services=services,
        prometheus_url=os.getenv("PROMETHEUS_URL", "http://127.0.0.1:19090"),
        grafana_url=os.getenv("GRAFANA_URL", "http://127.0.0.1:13000"),
    )


@router.get("/logs", response_model=AdminLogListResponse, summary="List derived error logs")
def list_logs(
    session: DbSession,
    admin_user: AdminUser,
    limit: Annotated[int, Query(gt=0, le=200)] = 50,
) -> AdminLogListResponse:
    """Return UI-visible errors available in the current database model."""

    failed_predictions = (
        session.execute(
            select(PredictionTask)
            .where(PredictionTask.status == "failed")
            .options(selectinload(PredictionTask.user), selectinload(PredictionTask.model))
            .order_by(PredictionTask.updated_at.desc(), PredictionTask.id.desc())
            .limit(limit),
        )
        .scalars()
        .all()
    )
    items = [
        AdminLogRead(
            created_at=prediction.updated_at,
            level="ERROR",
            source="prediction",
            message=prediction.error_message or "Prediction failed",
            user_id=prediction.user_id,
            user_email=prediction.user.email if prediction.user is not None else None,
            related_object=f"prediction:{prediction.id}; model:{prediction.model_id}",
        )
        for prediction in failed_predictions
    ]
    return AdminLogListResponse(items=items, total=len(items))


__all__ = ["router"]
