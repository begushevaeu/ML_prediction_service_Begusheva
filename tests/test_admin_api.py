"""Admin API tests."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.predictions.router as predictions_router
from app.auth.passwords import hash_password
from app.billing.service import credit_user_balance, debit_prediction_success
from app.core.config import Settings, get_settings
from app.db import Base
from app.db.models import CreditBalance, MLModel, Payment, PredictionTask, Role, User
from app.db.session import get_db_session
from app.main import create_app
from app.users.service import ADMIN_ROLE
from tests.test_predictions_api import FakeTask, auth_headers, login_user, register_user

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
def client(db_session: Session) -> Generator[TestClient]:
    app = create_app(TEST_SETTINGS)

    def override_db_session() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS

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


def seed_platform_data(db_session: Session, tmp_path: Path) -> int:
    owner = db_session.get(User, 1)
    assert owner is not None
    model_path = tmp_path / "admin-model.joblib"
    model_path.write_bytes(b"trusted test artifact")
    model = MLModel(
        owner=owner,
        name="Admin model",
        storage_path=str(model_path),
        status="uploaded",
        model_metadata={"description": "Admin test model"},
    )
    db_session.add(model)
    db_session.flush()

    payment = Payment(
        user=owner,
        provider="mock",
        provider_payment_id="mock_admin_test",
        status="succeeded",
        credits_purchased=5,
        amount_cents=250,
        currency="USD",
    )
    prediction = PredictionTask(
        user=owner,
        model=model,
        status="succeeded",
        input_payload={"rows": [[1]]},
        result_payload={"predictions": [1]},
    )
    db_session.add_all([payment, prediction])
    db_session.flush()
    credit_user_balance(
        db_session,
        user_id=owner.id,
        amount_credits=5,
        transaction_type="payment_credit",
        payment_id=payment.id,
    )
    debit_prediction_success(
        db_session,
        user_id=owner.id,
        prediction_task_id=prediction.id,
        amount_credits=1,
    )
    db_session.commit()
    return model.id


def test_regular_user_cannot_access_admin_api(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    response = client.get("/api/v1/admin/users", headers=auth_headers(token))

    assert response.status_code == 403


def test_admin_summary_and_global_lists_use_real_data(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    register_user(client)
    create_admin(db_session)
    seed_platform_data(db_session, tmp_path)
    admin_token = login_user(client, email="admin@example.com", password="admin-password")
    headers = auth_headers(admin_token)

    summary = client.get("/api/v1/admin/dashboard/summary", headers=headers)
    users = client.get("/api/v1/admin/users", headers=headers)
    models = client.get("/api/v1/admin/models", headers=headers)
    predictions = client.get("/api/v1/admin/predictions", headers=headers)
    payments = client.get("/api/v1/admin/payments", headers=headers)
    transactions = client.get("/api/v1/admin/billing/transactions", headers=headers)

    assert summary.status_code == 200
    assert summary.json()["users_total"] == 2
    assert summary.json()["predictions_succeeded"] == 1
    assert summary.json()["credits_debited"] == 1
    assert users.json()["total"] == 2
    assert models.json()["items"][0]["runs_count"] == 1
    assert predictions.json()["items"][0]["cost_credits"] == 1
    assert payments.json()["items"][0]["credits_purchased"] == 5
    assert transactions.json()["total"] == 2


def test_admin_can_block_and_unblock_user(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    create_admin(db_session)
    admin_token = login_user(client, email="admin@example.com", password="admin-password")

    blocked = client.patch(
        "/api/v1/admin/users/1/status",
        headers=auth_headers(admin_token),
        json={"is_active": False},
    )
    blocked_login = client.post(
        "/api/v1/auth/login",
        data={"username": "owner@example.com", "password": "strong-password"},
    )
    unblocked = client.patch(
        "/api/v1/admin/users/1/status",
        headers=auth_headers(admin_token),
        json={"is_active": True},
    )

    assert blocked.status_code == 200
    assert blocked.json()["is_active"] is False
    assert blocked_login.status_code == 401
    assert unblocked.status_code == 200
    assert unblocked.json()["is_active"] is True


def test_admin_soft_deleted_model_cannot_be_used_for_prediction(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_user(client)
    user_token = login_user(client)
    create_admin(db_session)
    model_id = seed_platform_data(db_session, tmp_path)
    admin_token = login_user(client, email="admin@example.com", password="admin-password")

    delete_response = client.delete(
        f"/api/v1/admin/models/{model_id}",
        headers=auth_headers(admin_token),
    )
    fake_task = FakeTask()
    monkeypatch.setattr(predictions_router, "run_prediction_task", fake_task)
    prediction_response = client.post(
        "/api/v1/predictions",
        headers=auth_headers(user_token),
        json={"model_id": model_id, "input_payload": {"rows": [[1]]}},
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"
    assert prediction_response.status_code == 404
    assert fake_task.prediction_ids == []
