"""Base REST API contract tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.passwords import hash_password
from app.core.config import Settings, get_settings
from app.db import Base
from app.db.models import CreditBalance, MLModel, Role, User
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


def test_openapi_exposes_base_api_contracts(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/models" in paths
    assert "/api/v1/models/{model_id}" in paths
    assert "/api/v1/predictions" in paths
    assert "/api/v1/predictions/{prediction_id}" in paths
    assert "/api/v1/billing/balance" in paths
    assert "/api/v1/billing/transactions" in paths
    assert "/api/v1/payments" in paths
    assert "/api/v1/payments/{payment_id}" in paths
    assert "/api/v1/payments/{payment_id}/confirm" in paths


def test_empty_domain_lists_and_balance_are_available(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)
    headers = auth_headers(token)

    balance_response = client.get("/api/v1/billing/balance", headers=headers)
    assert balance_response.status_code == 200
    assert balance_response.json()["credits_available"] == 0

    for endpoint in (
        "/api/v1/models",
        "/api/v1/predictions",
        "/api/v1/billing/transactions",
        "/api/v1/payments",
    ):
        response = client.get(endpoint, headers=headers)
        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0


def test_model_lookup_returns_only_current_users_model(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    token = login_user(client)
    owner = db_session.get(User, 1)
    assert owner is not None
    model = MLModel(
        owner=owner,
        name="Churn model",
        storage_path="/tmp/churn.joblib",
        model_metadata={"target": "churn"},
    )
    db_session.add(model)
    db_session.commit()
    db_session.refresh(model)

    response = client.get(f"/api/v1/models/{model.id}", headers=auth_headers(token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Churn model"
    assert payload["metadata"] == {"target": "churn"}

    other_role = Role(name="other-role", description="Other role")
    other_user = User(
        email="other@example.com",
        password_hash=hash_password("strong-password"),
        full_name="Other",
        role=other_role,
    )
    other_user.credit_balance = CreditBalance(credits_available=0)
    db_session.add(other_user)
    db_session.commit()

    other_token = login_user(client, email="other@example.com", password="strong-password")
    other_response = client.get(f"/api/v1/models/{model.id}", headers=auth_headers(other_token))

    assert other_response.status_code == 404
    assert other_response.json()["error"]["code"] == "404"


def test_prediction_validation_and_payment_create_contracts(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)
    headers = auth_headers(token)

    invalid_prediction = client.post(
        "/api/v1/predictions",
        json={"model_id": 0, "input_payload": {}},
        headers=headers,
    )
    assert invalid_prediction.status_code == 422
    assert invalid_prediction.json()["error"]["code"] == "validation_error"

    payment_response = client.post(
        "/api/v1/payments",
        json={"credits_purchased": 10, "amount_cents": 500, "currency": "usd"},
        headers=headers,
    )
    assert payment_response.status_code == 201
    assert payment_response.json()["status"] == "pending"
    assert payment_response.json()["currency"] == "USD"


def test_unified_error_shape_for_auth_and_permissions(client: TestClient) -> None:
    unauthenticated = client.get("/api/v1/users/me")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "401"
    assert unauthenticated.headers["www-authenticate"] == "Bearer"

    register_user(client)
    token = login_user(client)

    forbidden = client.get("/api/v1/users/admin-check", headers=auth_headers(token))

    assert forbidden.status_code == 403
    assert forbidden.json() == {
        "error": {
            "code": "403",
            "message": "Not enough permissions",
        },
    }
