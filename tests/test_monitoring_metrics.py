"""Monitoring metrics endpoint tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.passwords import hash_password
from app.core.config import Settings, get_settings
from app.db import Base
from app.db.models import (
    BillingTransaction,
    CreditBalance,
    MLModel,
    Payment,
    PredictionTask,
    PromoCode,
    PromoRedemption,
    Role,
    User,
)
from app.db.session import get_db_session
from app.main import create_app
from app.monitoring.metrics import reset_metrics_for_tests

TEST_SETTINGS = Settings(
    app_env="test",
    jwt_secret_key="test-secret-with-at-least-thirty-two-bytes",
)


@pytest.fixture
def db_session() -> Generator[Session]:
    reset_metrics_for_tests()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with testing_session() as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()
    reset_metrics_for_tests()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient]:
    app = create_app(TEST_SETTINGS)

    def override_db_session() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS

    with TestClient(app) as test_client:
        yield test_client


def seed_monitoring_records(session: Session) -> None:
    role = Role(name="user", description="Default user")
    user = User(
        email="metrics@example.com",
        password_hash=hash_password("strong-password"),
        full_name="Metrics User",
        role=role,
    )
    balance = CreditBalance(user=user, credits_available=7)
    model = MLModel(
        owner=user,
        name="Metrics model",
        storage_path="/tmp/metrics.joblib",
        framework="scikit-learn",
        status="uploaded",
    )
    prediction = PredictionTask(
        user=user,
        model=model,
        status="succeeded",
        input_payload={"rows": [[1]]},
        result_payload={"predictions": [1]},
    )
    payment = Payment(
        user=user,
        status="succeeded",
        credits_purchased=8,
        amount_cents=500,
        currency="USD",
    )
    promo_code = PromoCode(
        code="METRICS",
        credit_amount=2,
        redemptions_count=1,
        is_active=True,
    )
    redemption = PromoRedemption(
        user=user,
        promo_code=promo_code,
        credits_granted=2,
    )
    transaction = BillingTransaction(
        user=user,
        balance=balance,
        prediction_task=prediction,
        transaction_type="prediction_debit",
        direction="debit",
        amount_credits=1,
        balance_after_credits=6,
        status="posted",
    )
    session.add_all(
        [
            role,
            user,
            balance,
            model,
            prediction,
            payment,
            promo_code,
            redemption,
            transaction,
        ],
    )
    session.commit()


def test_metrics_endpoint_exposes_http_and_business_metrics(
    client: TestClient,
    db_session: Session,
) -> None:
    seed_monitoring_records(db_session)

    health_response = client.get("/api/v1/health")
    missing_response = client.get("/does-not-exist")
    metrics_response = client.get("/metrics")

    assert health_response.status_code == 200
    assert missing_response.status_code == 404
    assert metrics_response.status_code == 200
    assert metrics_response.headers["content-type"].startswith("text/plain")

    metrics = metrics_response.text
    assert "# HELP ml_http_requests_total Total HTTP requests." in metrics
    assert (
        'ml_http_requests_total{method="GET",path="/api/v1/health",status_code="200"} 1' in metrics
    )
    assert (
        'ml_http_request_errors_total{method="GET",path="/does-not-exist",status_code="404"} 1'
        in metrics
    )
    assert 'ml_prediction_tasks{status="succeeded"} 1' in metrics
    assert 'ml_worker_prediction_tasks_completed{status="succeeded"} 1' in metrics
    assert "ml_credit_balance_available 7" in metrics
    assert (
        'ml_billing_transactions{direction="debit",status="posted",'
        'transaction_type="prediction_debit"} 1'
    ) in metrics
    assert 'ml_models{status="uploaded"} 1' in metrics
    assert 'ml_payments{status="succeeded"} 1' in metrics
    assert "ml_promo_redemptions 1" in metrics
