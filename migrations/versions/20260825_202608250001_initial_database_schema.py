"""Initial database schema.

Revision ID: 202608250001
Revises:
Create Date: 2026-08-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608250001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    """Return standard timestamp columns for MVP tables."""

    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    """Apply the initial schema."""

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("name", name=op.f("uq_roles_name")),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_users_role_id_roles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_index("ix_users_role_active", "users", ["role_id", "is_active"])

    op.create_table(
        "credit_balances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("credits_available", sa.Integer(), server_default=sa.text("0"), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "credits_available >= 0",
            name=op.f("ck_credit_balances_credits_available_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_credit_balances_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_balances")),
        sa.UniqueConstraint("user_id", name=op.f("uq_credit_balances_user_id")),
    )

    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column(
            "framework",
            sa.String(length=50),
            server_default="scikit-learn",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=30), server_default="uploaded", nullable=False),
        sa.Column("model_metadata", sa.JSON(), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_ml_models_owner_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ml_models")),
    )
    op.create_index("ix_ml_models_owner_id", "ml_models", ["owner_id"])
    op.create_index("ix_ml_models_owner_status", "ml_models", ["owner_id", "status"])
    op.create_index("ix_ml_models_status", "ml_models", ["status"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), server_default="mock", nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("credits_purchased", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "credits_purchased > 0",
            name=op.f("ck_payments_credits_purchased_positive"),
        ),
        sa.CheckConstraint("amount_cents >= 0", name=op.f("ck_payments_amount_cents_non_negative")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_payments_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint("provider_payment_id", name=op.f("uq_payments_provider_payment_id")),
    )
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_user_status", "payments", ["user_id", "status"])

    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("credit_amount", sa.Integer(), nullable=False),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("redemptions_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "credit_amount > 0",
            name=op.f("ck_promo_codes_credit_amount_positive"),
        ),
        sa.CheckConstraint(
            "redemptions_count >= 0",
            name=op.f("ck_promo_codes_redemptions_count_non_negative"),
        ),
        sa.CheckConstraint(
            "max_redemptions IS NULL OR max_redemptions > 0",
            name=op.f("ck_promo_codes_max_redemptions_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_promo_codes_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_promo_codes")),
        sa.UniqueConstraint("code", name=op.f("uq_promo_codes_code")),
    )
    op.create_index("ix_promo_codes_active_expires", "promo_codes", ["is_active", "expires_at"])

    op.create_table(
        "prediction_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["ml_models.id"],
            name=op.f("fk_prediction_tasks_model_id_ml_models"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_prediction_tasks_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prediction_tasks")),
        sa.UniqueConstraint("celery_task_id", name=op.f("uq_prediction_tasks_celery_task_id")),
    )
    op.create_index("ix_prediction_tasks_model_id", "prediction_tasks", ["model_id"])
    op.create_index("ix_prediction_tasks_model_status", "prediction_tasks", ["model_id", "status"])
    op.create_index("ix_prediction_tasks_status", "prediction_tasks", ["status"])
    op.create_index("ix_prediction_tasks_user_id", "prediction_tasks", ["user_id"])
    op.create_index("ix_prediction_tasks_user_status", "prediction_tasks", ["user_id", "status"])

    op.create_table(
        "promo_redemptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("promo_code_id", sa.Integer(), nullable=False),
        sa.Column("credits_granted", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "credits_granted > 0",
            name=op.f("ck_promo_redemptions_credits_granted_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["promo_code_id"],
            ["promo_codes.id"],
            name=op.f("fk_promo_redemptions_promo_code_id_promo_codes"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_promo_redemptions_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_promo_redemptions")),
        sa.UniqueConstraint(
            "user_id",
            "promo_code_id",
            name="uq_promo_redemptions_user_code",
        ),
    )
    op.create_index(
        "ix_promo_redemptions_promo_code_id",
        "promo_redemptions",
        ["promo_code_id"],
    )
    op.create_index(
        "ix_promo_redemptions_user_code",
        "promo_redemptions",
        ["user_id", "promo_code_id"],
    )
    op.create_index("ix_promo_redemptions_user_id", "promo_redemptions", ["user_id"])

    op.create_table(
        "billing_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("balance_id", sa.Integer(), nullable=False),
        sa.Column("prediction_task_id", sa.Integer(), nullable=True),
        sa.Column("payment_id", sa.Integer(), nullable=True),
        sa.Column("promo_redemption_id", sa.Integer(), nullable=True),
        sa.Column("transaction_type", sa.String(length=40), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("amount_credits", sa.Integer(), nullable=False),
        sa.Column("balance_after_credits", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="posted", nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "amount_credits > 0",
            name=op.f("ck_billing_transactions_amount_credits_positive"),
        ),
        sa.CheckConstraint(
            "balance_after_credits >= 0",
            name=op.f("ck_billing_transactions_balance_after_credits_non_negative"),
        ),
        sa.CheckConstraint(
            "direction IN ('credit', 'debit')",
            name=op.f("ck_billing_transactions_direction_allowed"),
        ),
        sa.CheckConstraint(
            "transaction_type IN "
            "('payment_credit', 'prediction_debit', 'promo_credit', 'adjustment')",
            name=op.f("ck_billing_transactions_transaction_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'posted', 'voided')",
            name=op.f("ck_billing_transactions_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["balance_id"],
            ["credit_balances.id"],
            name=op.f("fk_billing_transactions_balance_id_credit_balances"),
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_billing_transactions_payment_id_payments"),
        ),
        sa.ForeignKeyConstraint(
            ["prediction_task_id"],
            ["prediction_tasks.id"],
            name=op.f("fk_billing_transactions_prediction_task_id_prediction_tasks"),
        ),
        sa.ForeignKeyConstraint(
            ["promo_redemption_id"],
            ["promo_redemptions.id"],
            name=op.f("fk_billing_transactions_promo_redemption_id_promo_redemptions"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_billing_transactions_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_transactions")),
        sa.UniqueConstraint(
            "idempotency_key", name=op.f("uq_billing_transactions_idempotency_key")
        ),
    )
    op.create_index(
        "ix_billing_transactions_balance_id",
        "billing_transactions",
        ["balance_id"],
    )
    op.create_index(
        "ix_billing_transactions_payment_id",
        "billing_transactions",
        ["payment_id"],
    )
    op.create_index(
        "ix_billing_transactions_prediction_task_id",
        "billing_transactions",
        ["prediction_task_id"],
    )
    op.create_index(
        "ix_billing_transactions_promo_redemption_id",
        "billing_transactions",
        ["promo_redemption_id"],
    )
    op.create_index("ix_billing_transactions_status", "billing_transactions", ["status"])
    op.create_index(
        "ix_billing_transactions_user_created",
        "billing_transactions",
        ["user_id", "created_at"],
    )
    op.create_index("ix_billing_transactions_user_id", "billing_transactions", ["user_id"])
    op.create_index(
        "ix_billing_transactions_user_type",
        "billing_transactions",
        ["user_id", "transaction_type"],
    )


def downgrade() -> None:
    """Revert the initial schema."""

    op.drop_table("billing_transactions")
    op.drop_table("promo_redemptions")
    op.drop_table("prediction_tasks")
    op.drop_table("promo_codes")
    op.drop_table("payments")
    op.drop_table("ml_models")
    op.drop_table("credit_balances")
    op.drop_table("users")
    op.drop_table("roles")
