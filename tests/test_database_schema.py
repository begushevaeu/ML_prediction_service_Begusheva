"""Database schema tests."""

from alembic.config import Config
from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from app.core.config import Settings
from app.db import Base
from app.db.models import BillingTransaction, CreditBalance, PromoRedemption

EXPECTED_TABLES = {
    "roles",
    "users",
    "credit_balances",
    "ml_models",
    "prediction_tasks",
    "billing_transactions",
    "payments",
    "promo_codes",
    "promo_redemptions",
}


def constraint_columns(constraint: UniqueConstraint) -> tuple[str, ...]:
    return tuple(column.name for column in constraint.columns)


def index_columns(index: Index) -> tuple[str, ...]:
    return tuple(column.name for column in index.columns)


def test_database_metadata_declares_mvp_tables() -> None:
    assert EXPECTED_TABLES.issubset(Base.metadata.tables)
    assert "credit_packages" not in Base.metadata.tables


def test_credit_balance_is_single_common_balance_per_user() -> None:
    table = CreditBalance.__table__

    assert table.c.credits_available.default.arg == 0
    assert any(
        isinstance(constraint, UniqueConstraint) and constraint_columns(constraint) == ("user_id",)
        for constraint in table.constraints
    )
    assert any(
        isinstance(constraint, CheckConstraint)
        and "credits_available >= 0" in str(constraint.sqltext)
        for constraint in table.constraints
    )


def test_promo_redemption_prevents_repeated_user_activation() -> None:
    table = PromoRedemption.__table__

    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint_columns(constraint) == ("user_id", "promo_code_id")
        for constraint in table.constraints
    )


def test_billing_transactions_are_indexed_for_user_history() -> None:
    table = BillingTransaction.__table__
    indexes = {index_columns(index) for index in table.indexes}

    assert ("user_id", "created_at") in indexes
    assert ("user_id", "transaction_type") in indexes
    assert table.c.idempotency_key.unique is True


def test_prediction_price_defaults_to_one_credit() -> None:
    assert Settings().prediction_price_credits == 1


def test_alembic_points_to_migrations_folder() -> None:
    config = Config("alembic.ini")

    assert config.get_main_option("script_location") == "migrations"
