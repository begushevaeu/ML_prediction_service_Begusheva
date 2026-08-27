"""Admin API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AdminDashboardSummaryRead(BaseModel):
    """Top-level platform metrics for the admin dashboard."""

    users_total: int
    users_active: int
    models_total: int
    predictions_total: int
    predictions_succeeded: int
    predictions_failed: int
    prediction_success_rate: float
    credits_debited: int
    credits_credited: int
    credits_purchased: int
    payments_total: int
    payments_succeeded: int
    promo_codes_total: int
    promo_redemptions_total: int


class AdminActivityPointRead(BaseModel):
    """Prediction activity bucket."""

    date: str
    predictions_total: int
    predictions_succeeded: int
    predictions_failed: int


class AdminActivityResponse(BaseModel):
    """Prediction activity response."""

    period: Literal["day", "week", "month"]
    items: list[AdminActivityPointRead]


class AdminEventRead(BaseModel):
    """Derived platform activity event."""

    created_at: datetime
    event_type: str
    message: str
    severity: str
    user_id: int | None = None
    user_email: str | None = None
    related_object: str | None = None


class AdminEventListResponse(BaseModel):
    """Derived platform activity feed."""

    items: list[AdminEventRead]
    total: int


class AdminUserRead(BaseModel):
    """Admin-visible user row."""

    id: int
    email: str
    full_name: str | None
    role: str
    is_active: bool
    credits_available: int
    created_at: datetime
    updated_at: datetime


class AdminUserListResponse(BaseModel):
    """Admin user list."""

    items: list[AdminUserRead]
    total: int


class AdminUserDetailRead(AdminUserRead):
    """Admin-visible user detail with activity counts."""

    models_total: int
    predictions_total: int
    payments_total: int
    transactions_total: int


class AdminUserStatusUpdate(BaseModel):
    """Admin request to activate or deactivate a user."""

    is_active: bool


class AdminModelRead(BaseModel):
    """Admin-visible ML model row."""

    id: int
    name: str
    owner_id: int
    owner_email: str
    framework: str
    status: str
    runs_count: int
    metadata: dict[str, object] | None
    created_at: datetime
    updated_at: datetime


class AdminModelListResponse(BaseModel):
    """Admin model list."""

    items: list[AdminModelRead]
    total: int


class AdminPredictionRead(BaseModel):
    """Admin-visible prediction row."""

    id: int
    user_id: int
    user_email: str
    model_id: int
    model_name: str
    status: str
    cost_credits: int
    result_payload: dict[str, object] | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminPredictionListResponse(BaseModel):
    """Admin prediction list."""

    items: list[AdminPredictionRead]
    total: int


class AdminPaymentRead(BaseModel):
    """Admin-visible payment row."""

    id: int
    user_id: int
    user_email: str
    provider: str
    provider_payment_id: str | None
    status: str
    credits_purchased: int
    amount_cents: int
    currency: str
    created_at: datetime
    updated_at: datetime


class AdminPaymentListResponse(BaseModel):
    """Admin payment list."""

    items: list[AdminPaymentRead]
    total: int


class AdminBillingTransactionRead(BaseModel):
    """Admin-visible credit ledger row."""

    id: int
    user_id: int
    user_email: str
    transaction_type: str
    direction: str
    amount_credits: int
    balance_after_credits: int
    status: str
    description: str | None
    prediction_task_id: int | None
    payment_id: int | None
    promo_redemption_id: int | None
    created_at: datetime


class AdminBillingTransactionListResponse(BaseModel):
    """Admin credit ledger list."""

    items: list[AdminBillingTransactionRead]
    total: int


class AdminPromoRedemptionRead(BaseModel):
    """Admin-visible promo redemption row."""

    id: int
    promo_code_id: int
    code: str
    user_id: int
    user_email: str
    credits_granted: int
    created_at: datetime


class AdminPromoRedemptionListResponse(BaseModel):
    """Admin promo redemption list."""

    items: list[AdminPromoRedemptionRead]
    total: int


class AdminSystemSettingsRead(BaseModel):
    """Safe runtime settings for admin review."""

    app_name: str
    app_env: str
    api_v1_prefix: str
    prediction_price_credits: int
    max_model_upload_size_bytes: int
    access_token_expire_minutes: int
    bootstrap_local_admin: bool


class AdminSystemUsageRead(BaseModel):
    """Small system usage summary."""

    cpu_percent: float | None = None
    ram_percent: float | None = None
    disk_percent: float | None = None


class AdminServiceStatusRead(BaseModel):
    """Service status row."""

    name: str
    status: str
    details: str | None = None


class AdminMonitoringSummaryRead(BaseModel):
    """Admin monitoring summary."""

    system_usage: AdminSystemUsageRead
    services: list[AdminServiceStatusRead]
    prometheus_url: str = Field(default="http://127.0.0.1:19090")
    grafana_url: str = Field(default="http://127.0.0.1:13000")


class AdminLogRead(BaseModel):
    """Admin-visible derived log/error row."""

    created_at: datetime
    level: str
    source: str
    message: str
    user_id: int | None = None
    user_email: str | None = None
    related_object: str | None = None


class AdminLogListResponse(BaseModel):
    """Admin logs/errors response."""

    items: list[AdminLogRead]
    total: int


__all__ = [
    "AdminActivityPointRead",
    "AdminActivityResponse",
    "AdminBillingTransactionListResponse",
    "AdminBillingTransactionRead",
    "AdminDashboardSummaryRead",
    "AdminEventListResponse",
    "AdminEventRead",
    "AdminLogListResponse",
    "AdminLogRead",
    "AdminModelListResponse",
    "AdminModelRead",
    "AdminMonitoringSummaryRead",
    "AdminPaymentListResponse",
    "AdminPaymentRead",
    "AdminPredictionListResponse",
    "AdminPredictionRead",
    "AdminPromoRedemptionListResponse",
    "AdminPromoRedemptionRead",
    "AdminServiceStatusRead",
    "AdminSystemSettingsRead",
    "AdminSystemUsageRead",
    "AdminUserDetailRead",
    "AdminUserListResponse",
    "AdminUserRead",
    "AdminUserStatusUpdate",
]
