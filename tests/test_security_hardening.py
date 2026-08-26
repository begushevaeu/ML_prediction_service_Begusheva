"""Security hardening tests for sensitive MVP boundaries."""

import pickle
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.passwords import verify_password
from app.auth.tokens import TokenError, create_access_token, decode_access_token
from app.core.config import Settings, get_settings
from app.db import Base
from app.db.models import CreditBalance, Role, User
from app.db.session import get_db_session
from app.main import create_app

TEST_SECRET = "test-secret-with-at-least-thirty-two-bytes"
PRODUCTION_SECRET = "production-secret-with-at-least-thirty-two-bytes"


class TinyEstimator:
    """Small pickle-friendly estimator used by upload hardening tests."""

    def predict(self, rows: list[object]) -> list[int]:
        return [0 for _ in rows]


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


def build_client(db_session: Session, settings: Settings) -> TestClient:
    app = create_app(settings)

    def override_db_session() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def register_user(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@example.com",
            "password": "strong-password",
            "full_name": "Project Owner",
        },
    )
    assert response.status_code == 201


def login_user(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "owner@example.com", "password": "strong-password"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_production_env_rejects_default_jwt_secret() -> None:
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        create_app(Settings(app_env="production"))


def test_production_env_rejects_debug_mode() -> None:
    with pytest.raises(RuntimeError, match="APP_DEBUG"):
        create_app(
            Settings(
                app_env="production",
                app_debug=True,
                jwt_secret_key=PRODUCTION_SECRET,
            ),
        )


def test_unsupported_jwt_algorithm_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="JWT_ALGORITHM"):
        create_app(
            Settings(
                app_env="test",
                jwt_secret_key=TEST_SECRET,
                jwt_algorithm="none",
            ),
        )


def test_expired_access_token_is_rejected() -> None:
    settings = Settings(app_env="test", jwt_secret_key=TEST_SECRET)
    token = jwt.encode(
        {
            "sub": "1",
            "iat": datetime.now(UTC) - timedelta(minutes=10),
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(TokenError):
        decode_access_token(token, settings)


def test_inactive_user_token_is_rejected(
    db_session: Session,
) -> None:
    settings = Settings(app_env="test", jwt_secret_key=TEST_SECRET)
    client = build_client(db_session, settings)
    role = Role(name="user", description="Default user")
    user = User(
        email="inactive@example.com",
        password_hash="unused",
        full_name="Inactive User",
        role=role,
        is_active=False,
    )
    user.credit_balance = CreditBalance(credits_available=0)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(str(user.id), settings)

    response = client.get("/api/v1/users/me", headers=auth_headers(token))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "401"


def test_verify_password_rejects_malformed_hashes_without_error() -> None:
    malformed_hashes = [
        "",
        "pbkdf2_sha256$not-int$salt$digest",
        "pbkdf2_sha256$0$salt$digest",
        "pbkdf2_sha256$260000$salt$not valid base64",
        "unknown$260000$salt$digest",
    ]

    for password_hash in malformed_hashes:
        assert not verify_password("strong-password", password_hash)


def test_model_upload_sanitizes_filename_and_hides_storage_path(
    db_session: Session,
    tmp_path: Path,
) -> None:
    settings = Settings(
        app_env="test",
        jwt_secret_key=TEST_SECRET,
        model_storage_path=str(tmp_path / "models"),
    )
    client = build_client(db_session, settings)
    register_user(client)
    token = login_user(client)

    response = client.post(
        "/api/v1/models",
        headers=auth_headers(token),
        data={"name": "Sanitized model"},
        files={
            "file": (
                "..\\secret\\tiny.pkl",
                pickle.dumps(TinyEstimator()),
                "application/octet-stream",
            ),
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["metadata"]["uploaded_filename"] == "tiny.pkl"
    assert "storage_path" not in payload
    assert str(tmp_path) not in response.text
