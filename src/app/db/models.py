"""Database models for the MVP domain."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    """Common created/updated timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Role(TimestampMixin, Base):
    """User role such as user or admin."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(255))

    users: Mapped[list[User]] = relationship(back_populates="role")


class User(TimestampMixin, Base):
    """Registered application user."""

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_role_active", "role_id", "is_active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)

    role: Mapped[Role] = relationship(back_populates="users")
    credit_balance: Mapped[CreditBalance] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    ml_models: Mapped[list[MLModel]] = relationship(back_populates="owner")
    prediction_tasks: Mapped[list[PredictionTask]] = relationship(back_populates="user")
    billing_transactions: Mapped[list[BillingTransaction]] = relationship(back_populates="user")
    payments: Mapped[list[Payment]] = relationship(back_populates="user")
    promo_redemptions: Mapped[list[PromoRedemption]] = relationship(back_populates="user")


class CreditBalance(TimestampMixin, Base):
    """Single common credit balance for a user."""

    __tablename__ = "credit_balances"
    __table_args__ = (
        CheckConstraint("credits_available >= 0", name="credits_available_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    credits_available: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="credit_balance")
    billing_transactions: Mapped[list[BillingTransaction]] = relationship(
        back_populates="balance",
    )


class MLModel(TimestampMixin, Base):
    """Uploaded Scikit-learn model metadata."""

    __tablename__ = "ml_models"
    __table_args__ = (Index("ix_ml_models_owner_status", "owner_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    framework: Mapped[str] = mapped_column(
        String(50),
        default="scikit-learn",
        server_default="scikit-learn",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default="uploaded",
        server_default="uploaded",
        nullable=False,
        index=True,
    )
    model_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)

    owner: Mapped[User] = relationship(back_populates="ml_models")
    prediction_tasks: Mapped[list[PredictionTask]] = relationship(back_populates="model")


class PredictionTask(TimestampMixin, Base):
    """Asynchronous prediction job requested by a user."""

    __tablename__ = "prediction_tasks"
    __table_args__ = (
        Index("ix_prediction_tasks_user_status", "user_id", "status"),
        Index("ix_prediction_tasks_model_status", "model_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("ml_models.id"), nullable=False, index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        server_default="pending",
        nullable=False,
        index=True,
    )
    input_payload: Mapped[dict[str, object] | None] = mapped_column(JSON)
    result_payload: Mapped[dict[str, object] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="prediction_tasks")
    model: Mapped[MLModel] = relationship(back_populates="prediction_tasks")
    billing_transactions: Mapped[list[BillingTransaction]] = relationship(
        back_populates="prediction_task",
    )


class Payment(TimestampMixin, Base):
    """Mock/sandbox payment used to add credits."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("credits_purchased > 0", name="credits_purchased_positive"),
        CheckConstraint("amount_cents >= 0", name="amount_cents_non_negative"),
        Index("ix_payments_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(
        String(50),
        default="mock",
        server_default="mock",
        nullable=False,
    )
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        server_default="pending",
        nullable=False,
        index=True,
    )
    credits_purchased: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        server_default="USD",
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="payments")
    billing_transactions: Mapped[list[BillingTransaction]] = relationship(
        back_populates="payment",
    )


class PromoCode(TimestampMixin, Base):
    """Fixed-credit promo code for the simplest marketing mechanic."""

    __tablename__ = "promo_codes"
    __table_args__ = (
        CheckConstraint("credit_amount > 0", name="credit_amount_positive"),
        CheckConstraint("redemptions_count >= 0", name="redemptions_count_non_negative"),
        CheckConstraint(
            "max_redemptions IS NULL OR max_redemptions > 0",
            name="max_redemptions_positive",
        ),
        Index("ix_promo_codes_active_expires", "is_active", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    credit_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    max_redemptions: Mapped[int | None] = mapped_column(Integer)
    redemptions_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    redemptions: Mapped[list[PromoRedemption]] = relationship(back_populates="promo_code")


class PromoRedemption(TimestampMixin, Base):
    """A user's one-time redemption of a promo code."""

    __tablename__ = "promo_redemptions"
    __table_args__ = (
        UniqueConstraint("user_id", "promo_code_id", name="uq_promo_redemptions_user_code"),
        CheckConstraint("credits_granted > 0", name="credits_granted_positive"),
        Index("ix_promo_redemptions_user_code", "user_id", "promo_code_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    promo_code_id: Mapped[int] = mapped_column(
        ForeignKey("promo_codes.id"),
        nullable=False,
        index=True,
    )
    credits_granted: Mapped[int] = mapped_column(Integer, nullable=False)

    user: Mapped[User] = relationship(back_populates="promo_redemptions")
    promo_code: Mapped[PromoCode] = relationship(back_populates="redemptions")
    billing_transactions: Mapped[list[BillingTransaction]] = relationship(
        back_populates="promo_redemption",
    )


class BillingTransaction(TimestampMixin, Base):
    """Immutable credit ledger row."""

    __tablename__ = "billing_transactions"
    __table_args__ = (
        CheckConstraint("amount_credits > 0", name="amount_credits_positive"),
        CheckConstraint("balance_after_credits >= 0", name="balance_after_credits_non_negative"),
        CheckConstraint("direction IN ('credit', 'debit')", name="direction_allowed"),
        CheckConstraint(
            "transaction_type IN "
            "('payment_credit', 'prediction_debit', 'promo_credit', 'adjustment')",
            name="transaction_type_allowed",
        ),
        CheckConstraint("status IN ('pending', 'posted', 'voided')", name="status_allowed"),
        Index("ix_billing_transactions_user_created", "user_id", "created_at"),
        Index("ix_billing_transactions_user_type", "user_id", "transaction_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    balance_id: Mapped[int] = mapped_column(
        ForeignKey("credit_balances.id"),
        nullable=False,
        index=True,
    )
    prediction_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("prediction_tasks.id"),
        index=True,
    )
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), index=True)
    promo_redemption_id: Mapped[int | None] = mapped_column(
        ForeignKey("promo_redemptions.id"),
        index=True,
    )
    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    amount_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        default="posted",
        server_default="posted",
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)

    user: Mapped[User] = relationship(back_populates="billing_transactions")
    balance: Mapped[CreditBalance] = relationship(back_populates="billing_transactions")
    prediction_task: Mapped[PredictionTask | None] = relationship(
        back_populates="billing_transactions",
    )
    payment: Mapped[Payment | None] = relationship(back_populates="billing_transactions")
    promo_redemption: Mapped[PromoRedemption | None] = relationship(
        back_populates="billing_transactions",
    )


__all__ = [
    "BillingTransaction",
    "CreditBalance",
    "MLModel",
    "Payment",
    "PredictionTask",
    "PromoCode",
    "PromoRedemption",
    "Role",
    "User",
]
