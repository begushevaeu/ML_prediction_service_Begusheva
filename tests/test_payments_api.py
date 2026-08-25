"""Mock payment flow tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db import Base
from app.db.models import BillingTransaction, CreditBalance
from app.db.session import get_db_session
from app.main import create_app

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


def register_user(
    client: TestClient,
    email: str = "owner@example.com",
    password: str = "strong-password",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Project Owner",
        },
    )
    assert response.status_code == 201
    return response.json()


def login_user(
    client: TestClient,
    email: str = "owner@example.com",
    password: str = "strong-password",
) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_payment(
    client: TestClient,
    token: str,
    *,
    credits_purchased: int = 10,
    amount_cents: int = 500,
    currency: str = "usd",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/payments",
        headers=auth_headers(token),
        json={
            "credits_purchased": credits_purchased,
            "amount_cents": amount_cents,
            "currency": currency,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_payment_stores_pending_payment_without_credits(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    token = login_user(client)

    payload = create_payment(client, token, credits_purchased=12, amount_cents=700, currency="eur")

    assert payload["provider"] == "mock"
    assert payload["provider_payment_id"].startswith("mock_")
    assert payload["status"] == "pending"
    assert payload["credits_purchased"] == 12
    assert payload["amount_cents"] == 700
    assert payload["currency"] == "EUR"

    balance = db_session.scalar(select(CreditBalance).where(CreditBalance.user_id == 1))
    assert balance is not None
    assert balance.credits_available == 0

    list_response = client.get("/api/v1/payments", headers=auth_headers(token))
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


def test_confirm_payment_credits_balance_and_ledger_once(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    token = login_user(client)
    payment = create_payment(client, token, credits_purchased=10)

    response = client.post(
        f"/api/v1/payments/{payment['id']}/confirm",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"

    balance = db_session.scalar(select(CreditBalance).where(CreditBalance.user_id == 1))
    assert balance is not None
    assert balance.credits_available == 10

    transaction = db_session.scalar(
        select(BillingTransaction).where(
            BillingTransaction.payment_id == payment["id"],
            BillingTransaction.transaction_type == "payment_credit",
        ),
    )
    assert transaction is not None
    assert transaction.amount_credits == 10
    assert transaction.balance_after_credits == 10

    repeated = client.post(
        f"/api/v1/payments/{payment['id']}/confirm",
        headers=auth_headers(token),
    )

    assert repeated.status_code == 200
    assert repeated.json()["status"] == "succeeded"
    assert balance.credits_available == 10
    transactions = (
        db_session.execute(
            select(BillingTransaction).where(BillingTransaction.payment_id == payment["id"]),
        )
        .scalars()
        .all()
    )
    assert len(transactions) == 1


def test_payment_detail_and_confirmation_are_owner_scoped(client: TestClient) -> None:
    register_user(client, email="owner@example.com")
    owner_token = login_user(client, email="owner@example.com")
    payment = create_payment(client, owner_token)
    register_user(client, email="other@example.com")
    other_token = login_user(client, email="other@example.com")

    detail_response = client.get(
        f"/api/v1/payments/{payment['id']}",
        headers=auth_headers(other_token),
    )
    confirm_response = client.post(
        f"/api/v1/payments/{payment['id']}/confirm",
        headers=auth_headers(other_token),
    )
    list_response = client.get("/api/v1/payments", headers=auth_headers(other_token))

    assert detail_response.status_code == 404
    assert confirm_response.status_code == 404
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []


def test_confirm_missing_payment_returns_404(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    response = client.post("/api/v1/payments/999/confirm", headers=auth_headers(token))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "404"
