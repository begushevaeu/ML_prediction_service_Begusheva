"""Authentication API tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.passwords import hash_password, verify_password
from app.core.config import Settings, get_settings
from app.db import Base
from app.db.models import CreditBalance, Role, User
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
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    return str(payload["access_token"])


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_password_hashes_verify_without_storing_plaintext() -> None:
    password_hash = hash_password("strong-password")

    assert "strong-password" not in password_hash
    assert verify_password("strong-password", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_register_user_creates_default_role_and_balance(
    client: TestClient,
    db_session: Session,
) -> None:
    payload = register_user(client, email="OWNER@Example.com")

    assert payload == {
        "id": 1,
        "email": "owner@example.com",
        "full_name": "Project Owner",
        "role": "user",
        "is_active": True,
    }

    user = db_session.get(User, 1)
    assert user is not None
    assert user.credit_balance is not None
    assert user.credit_balance.credits_available == 0
    assert user.role.name == "user"


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    register_user(client, email="owner@example.com")

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "OWNER@example.com",
            "password": "another-password",
            "full_name": "Duplicate",
        },
    )

    assert response.status_code == 409


def test_login_returns_token_and_me_uses_bearer_token(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    response = client.get("/api/v1/users/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"


def test_login_rejects_wrong_password(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "owner@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_protected_endpoint_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401


def test_current_user_can_update_allowed_profile_fields(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    response = client.patch(
        "/api/v1/users/me",
        json={"full_name": "Updated Owner"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Owner"


def test_logout_requires_token_and_returns_stateless_strategy(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    response = client.post("/api/v1/auth/logout", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["strategy"] == "discard bearer token on the client"


def test_user_role_is_forbidden_from_admin_check(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    response = client.get("/api/v1/users/admin-check", headers=auth_headers(token))

    assert response.status_code == 403


def test_admin_role_can_access_admin_check(
    client: TestClient,
    db_session: Session,
) -> None:
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

    token = login_user(client, email="admin@example.com", password="admin-password")
    response = client.get("/api/v1/users/admin-check", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "role": "admin"}
