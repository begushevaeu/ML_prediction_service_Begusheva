"""Billing API and ledger tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.predictions.router as predictions_router
from app.auth.passwords import hash_password
from app.billing.service import credit_user_balance
from app.core.config import Settings, get_settings
from app.db import Base
from app.db.models import CreditBalance, Role, User
from app.db.session import get_db_session
from app.main import create_app
from app.users.service import ADMIN_ROLE
from tests.test_predictions_api import (
    FakeTask,
    auth_headers,
    login_user,
    register_user,
    upload_model,
)

TEST_SETTINGS = Settings(
    app_env="test",
    jwt_secret_key="test-secret-with-at-least-thirty-two-bytes",
)


@pytest.fixture
def db_session() -> Generator[Session]:
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


@pytest.fixture
def client(db_session: Session, tmp_path) -> Generator[TestClient]:
    settings = Settings(
        app_env="test",
        jwt_secret_key="test-secret-with-at-least-thirty-two-bytes",
        model_storage_path=str(tmp_path / "models"),
    )
    app = create_app(settings)

    def override_db_session() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as test_client:
        yield test_client


def create_admin(db_session: Session) -> None:
    admin_role = Role(name=ADMIN_ROLE, description="Administrator")
    admin_user = User(
        email="admin@example.com",
        password_hash=hash_password("admin-password"),
        full_name="Admin",
        role=admin_role,
    )
    admin_user.credit_balance = CreditBalance(credits_available=0)
    db_session.add(admin_user)
    db_session.commit()


def test_admin_adjustment_credits_user_balance_and_ledger(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    create_admin(db_session)
    admin_token = login_user(client, email="admin@example.com", password="admin-password")

    response = client.post(
        "/api/v1/billing/adjustments",
        headers=auth_headers(admin_token),
        json={
            "user_id": 1,
            "direction": "credit",
            "amount_credits": 3,
            "description": "Manual test credit",
            "idempotency_key": "manual-credit-1",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["user_id"] == 1
    assert payload["direction"] == "credit"
    assert payload["amount_credits"] == 3
    assert payload["balance_after_credits"] == 3

    balance = db_session.scalar(select(CreditBalance).where(CreditBalance.user_id == 1))
    assert balance is not None
    assert balance.credits_available == 3

    repeated = client.post(
        "/api/v1/billing/adjustments",
        headers=auth_headers(admin_token),
        json={
            "user_id": 1,
            "direction": "credit",
            "amount_credits": 3,
            "description": "Manual test credit",
            "idempotency_key": "manual-credit-1",
        },
    )

    assert repeated.status_code == 201
    assert repeated.json()["id"] == payload["id"]
    assert balance.credits_available == 3


def test_regular_user_cannot_create_billing_adjustment(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    response = client.post(
        "/api/v1/billing/adjustments",
        headers=auth_headers(token),
        json={"user_id": 1, "direction": "credit", "amount_credits": 1},
    )

    assert response.status_code == 403


def test_prediction_requires_available_credits(
    client: TestClient,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_user(client)
    token = login_user(client)
    model_id = upload_model(client, token, tmp_path)
    fake_task = FakeTask()
    monkeypatch.setattr(predictions_router, "run_prediction_task", fake_task)

    response = client.post(
        "/api/v1/predictions",
        headers=auth_headers(token),
        json={"model_id": model_id, "input_payload": {"rows": [[1]]}},
    )

    assert response.status_code == 402
    assert response.json()["error"]["code"] == "insufficient_credits"
    assert fake_task.prediction_ids == []


def test_admin_debit_rejects_insufficient_balance(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    create_admin(db_session)
    admin_token = login_user(client, email="admin@example.com", password="admin-password")

    response = client.post(
        "/api/v1/billing/adjustments",
        headers=auth_headers(admin_token),
        json={"user_id": 1, "direction": "debit", "amount_credits": 1},
    )

    assert response.status_code == 402
    assert response.json()["error"]["code"] == "insufficient_credits"


def test_billing_transactions_list_returns_user_ledger(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    token = login_user(client)
    credit_user_balance(
        db_session,
        user_id=1,
        amount_credits=2,
        transaction_type="adjustment",
        description="Direct test credit",
    )
    db_session.commit()

    response = client.get("/api/v1/billing/transactions", headers=auth_headers(token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["transaction_type"] == "adjustment"
