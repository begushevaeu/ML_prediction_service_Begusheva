"""Promo code API tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.passwords import hash_password
from app.core.config import Settings, get_settings
from app.db import Base
from app.db.models import BillingTransaction, CreditBalance, PromoCode, Role, User
from app.db.session import get_db_session
from app.main import create_app
from app.users.service import ADMIN_ROLE

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


def create_promo_code(
    client: TestClient,
    admin_token: str,
    *,
    code: str = "launch10",
    credit_amount: int = 10,
    max_redemptions: int | None = None,
    is_active: bool = True,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "code": code,
        "credit_amount": credit_amount,
        "is_active": is_active,
    }
    if max_redemptions is not None:
        payload["max_redemptions"] = max_redemptions

    response = client.post(
        "/api/v1/promo-codes",
        headers=auth_headers(admin_token),
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


def test_admin_can_create_and_list_promo_codes(
    client: TestClient,
    db_session: Session,
) -> None:
    create_admin(db_session)
    admin_token = login_user(client, email="admin@example.com", password="admin-password")

    payload = create_promo_code(
        client,
        admin_token,
        code=" launch10 ",
        credit_amount=10,
        max_redemptions=2,
    )

    assert payload["code"] == "LAUNCH10"
    assert payload["credit_amount"] == 10
    assert payload["max_redemptions"] == 2
    assert payload["redemptions_count"] == 0

    duplicate = client.post(
        "/api/v1/promo-codes",
        headers=auth_headers(admin_token),
        json={"code": "launch10", "credit_amount": 5},
    )
    list_response = client.get("/api/v1/promo-codes", headers=auth_headers(admin_token))

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "promo_code_exists"
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


def test_regular_user_cannot_create_or_list_promo_codes(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    create_response = client.post(
        "/api/v1/promo-codes",
        headers=auth_headers(token),
        json={"code": "USER10", "credit_amount": 10},
    )
    list_response = client.get("/api/v1/promo-codes", headers=auth_headers(token))

    assert create_response.status_code == 403
    assert list_response.status_code == 403


def test_user_redeems_promo_once_crediting_balance_and_ledger(
    client: TestClient,
    db_session: Session,
) -> None:
    create_admin(db_session)
    admin_token = login_user(client, email="admin@example.com", password="admin-password")
    create_promo_code(client, admin_token, code="WELCOME5", credit_amount=5)
    register_user(client)
    token = login_user(client)

    response = client.post(
        "/api/v1/promo-codes/redeem",
        headers=auth_headers(token),
        json={"code": " welcome5 "},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "WELCOME5"
    assert payload["credits_granted"] == 5
    assert payload["balance_after_credits"] == 5

    balance = db_session.scalar(select(CreditBalance).where(CreditBalance.user_id == 2))
    assert balance is not None
    assert balance.credits_available == 5

    transaction = db_session.scalar(
        select(BillingTransaction).where(
            BillingTransaction.user_id == 2,
            BillingTransaction.transaction_type == "promo_credit",
        ),
    )
    assert transaction is not None
    assert transaction.amount_credits == 5

    promo_code = db_session.scalar(select(PromoCode).where(PromoCode.code == "WELCOME5"))
    assert promo_code is not None
    assert promo_code.redemptions_count == 1

    repeated = client.post(
        "/api/v1/promo-codes/redeem",
        headers=auth_headers(token),
        json={"code": "WELCOME5"},
    )
    redemptions = client.get("/api/v1/promo-codes/redemptions", headers=auth_headers(token))

    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "promo_already_redeemed"
    assert balance.credits_available == 5
    assert redemptions.status_code == 200
    assert redemptions.json()["total"] == 1


def test_promo_redemption_limit_is_enforced(
    client: TestClient,
    db_session: Session,
) -> None:
    create_admin(db_session)
    admin_token = login_user(client, email="admin@example.com", password="admin-password")
    create_promo_code(client, admin_token, code="ONEUSE", credit_amount=3, max_redemptions=1)
    register_user(client, email="first@example.com")
    first_token = login_user(client, email="first@example.com")
    register_user(client, email="second@example.com")
    second_token = login_user(client, email="second@example.com")

    first_response = client.post(
        "/api/v1/promo-codes/redeem",
        headers=auth_headers(first_token),
        json={"code": "ONEUSE"},
    )
    second_response = client.post(
        "/api/v1/promo-codes/redeem",
        headers=auth_headers(second_token),
        json={"code": "ONEUSE"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["error"]["code"] == "promo_limit_reached"


def test_inactive_and_missing_promo_codes_are_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    create_admin(db_session)
    admin_token = login_user(client, email="admin@example.com", password="admin-password")
    create_promo_code(client, admin_token, code="PAUSED", credit_amount=4, is_active=False)
    register_user(client)
    token = login_user(client)

    inactive = client.post(
        "/api/v1/promo-codes/redeem",
        headers=auth_headers(token),
        json={"code": "PAUSED"},
    )
    missing = client.post(
        "/api/v1/promo-codes/redeem",
        headers=auth_headers(token),
        json={"code": "MISSING"},
    )

    assert inactive.status_code == 409
    assert inactive.json()["error"]["code"] == "promo_not_active"
    assert missing.status_code == 404
