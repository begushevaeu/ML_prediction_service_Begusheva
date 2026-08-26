"""Cross-cutting acceptance tests for the Testing roadmap stage."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.passwords import hash_password
from app.billing.service import credit_user_balance, debit_user_balance
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


def test_validation_and_missing_route_share_error_envelope(client: TestClient) -> None:
    validation = client.post("/api/v1/auth/register", json={"email": "bad-email"})
    missing = client.get("/api/v1/does-not-exist")

    assert validation.status_code == 422
    assert validation.json()["error"]["code"] == "validation_error"
    assert validation.json()["error"]["message"]

    assert missing.status_code == 404
    assert missing.json() == {
        "error": {
            "code": "404",
            "message": "Not Found",
        },
    }


def test_user_data_is_isolated_across_domain_endpoints(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client, email="owner@example.com")
    owner_token = login_user(client, email="owner@example.com")
    register_user(client, email="other@example.com")
    other_token = login_user(client, email="other@example.com")

    owner = db_session.scalar(select(User).where(User.email == "owner@example.com"))
    assert owner is not None
    assert owner.credit_balance is not None
    owner.credit_balance.credits_available = 7

    model = MLModel(
        owner=owner,
        name="Owner model",
        storage_path="/tmp/owner-model.joblib",
        model_metadata={"purpose": "acceptance"},
    )
    prediction = PredictionTask(
        user=owner,
        model=model,
        status="succeeded",
        input_payload={"rows": [[1]]},
        result_payload={"predictions": [42]},
    )
    payment = Payment(
        user=owner,
        provider_payment_id="mock_acceptance_owner",
        status="succeeded",
        credits_purchased=7,
        amount_cents=350,
        currency="USD",
    )
    promo_code = PromoCode(code="OWNER7", credit_amount=7, redemptions_count=1)
    promo_redemption = PromoRedemption(
        user=owner,
        promo_code=promo_code,
        credits_granted=7,
    )
    db_session.add_all([model, prediction, payment, promo_code, promo_redemption])
    db_session.flush()

    transaction = BillingTransaction(
        user=owner,
        balance=owner.credit_balance,
        payment=payment,
        transaction_type="payment_credit",
        direction="credit",
        amount_credits=7,
        balance_after_credits=7,
        status="posted",
        description="Acceptance credit",
    )
    db_session.add(transaction)
    db_session.commit()

    owner_headers = auth_headers(owner_token)
    other_headers = auth_headers(other_token)
    for endpoint in (
        "/api/v1/models",
        "/api/v1/predictions",
        "/api/v1/billing/transactions",
        "/api/v1/payments",
        "/api/v1/promo-codes/redemptions",
    ):
        owner_response = client.get(endpoint, headers=owner_headers)
        other_response = client.get(endpoint, headers=other_headers)

        assert owner_response.status_code == 200
        assert owner_response.json()["total"] == 1
        assert other_response.status_code == 200
        assert other_response.json()["items"] == []
        assert other_response.json()["total"] == 0

    other_balance = client.get("/api/v1/billing/balance", headers=other_headers)
    assert other_balance.status_code == 200
    assert other_balance.json()["credits_available"] == 0

    for endpoint in (
        f"/api/v1/models/{model.id}",
        f"/api/v1/predictions/{prediction.id}",
        f"/api/v1/payments/{payment.id}",
    ):
        response = client.get(endpoint, headers=other_headers)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "404"


def test_billing_idempotency_prevents_duplicate_ledger_rows(db_session: Session) -> None:
    role = Role(name="user", description="Default user")
    user = User(
        email="billing@example.com",
        password_hash=hash_password("strong-password"),
        full_name="Billing User",
        role=role,
    )
    user.credit_balance = CreditBalance(credits_available=0)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    first_credit = credit_user_balance(
        db_session,
        user_id=user.id,
        amount_credits=5,
        transaction_type="adjustment",
        description="Initial acceptance credit",
        idempotency_key="acceptance:credit",
    )
    repeated_credit = credit_user_balance(
        db_session,
        user_id=user.id,
        amount_credits=5,
        transaction_type="adjustment",
        description="Initial acceptance credit",
        idempotency_key="acceptance:credit",
    )
    first_debit = debit_user_balance(
        db_session,
        user_id=user.id,
        amount_credits=2,
        transaction_type="prediction_debit",
        description="Acceptance debit",
        idempotency_key="acceptance:debit",
    )
    repeated_debit = debit_user_balance(
        db_session,
        user_id=user.id,
        amount_credits=2,
        transaction_type="prediction_debit",
        description="Acceptance debit",
        idempotency_key="acceptance:debit",
    )
    db_session.commit()

    assert repeated_credit.id == first_credit.id
    assert repeated_debit.id == first_debit.id

    balance = db_session.scalar(select(CreditBalance).where(CreditBalance.user_id == user.id))
    assert balance is not None
    assert balance.credits_available == 3

    transactions = db_session.scalars(
        select(BillingTransaction).order_by(BillingTransaction.id),
    ).all()
    assert [
        (item.direction, item.amount_credits, item.balance_after_credits) for item in transactions
    ] == [
        ("credit", 5, 5),
        ("debit", 2, 3),
    ]
