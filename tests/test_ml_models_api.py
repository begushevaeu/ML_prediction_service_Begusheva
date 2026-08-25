"""ML model upload API tests."""

import pickle
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db import Base
from app.db.models import MLModel
from app.db.session import get_db_session
from app.main import create_app


class TinyEstimator:
    """Small pickle-friendly estimator used by upload tests."""

    def predict(self, rows: list[object]) -> list[int]:
        return [0 for _ in rows]


def serialize_model(model: object) -> bytes:
    return pickle.dumps(model)


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
def client(db_session: Session, tmp_path: Path) -> Generator[TestClient]:
    settings = Settings(
        app_env="test",
        jwt_secret_key="test-secret-with-at-least-thirty-two-bytes",
        model_storage_path=str(tmp_path / "models"),
        max_model_upload_size_bytes=1024 * 1024,
    )
    app = create_app(settings)

    def override_db_session() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as test_client:
        yield test_client


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


def test_upload_model_stores_metadata_and_file(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    token = login_user(client)

    response = client.post(
        "/api/v1/models",
        headers=auth_headers(token),
        data={
            "name": "Tiny estimator",
            "metadata_json": '{"features": ["age"], "target": "score"}',
        },
        files={
            "file": (
                "tiny.pkl",
                serialize_model(TinyEstimator()),
                "application/octet-stream",
            ),
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Tiny estimator"
    assert payload["framework"] == "scikit-learn"
    assert payload["status"] == "uploaded"
    assert payload["metadata"]["uploaded_filename"] == "tiny.pkl"
    assert payload["metadata"]["model_type"].endswith(".TinyEstimator")
    assert payload["metadata"]["user_metadata"] == {
        "features": ["age"],
        "target": "score",
    }

    model = db_session.get(MLModel, payload["id"])
    assert model is not None
    assert Path(model.storage_path).exists()

    list_response = client.get("/api/v1/models", headers=auth_headers(token))
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    detail_response = client.get(f"/api/v1/models/{payload['id']}", headers=auth_headers(token))
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == payload["id"]


def test_upload_accepts_joblib_sklearn_model(client: TestClient, tmp_path: Path) -> None:
    from joblib import dump
    from sklearn.dummy import DummyRegressor

    register_user(client)
    token = login_user(client)
    model = DummyRegressor(strategy="mean")
    model.fit([[1], [2]], [10, 20])
    model_path = tmp_path / "dummy.joblib"
    dump(model, model_path)

    response = client.post(
        "/api/v1/models",
        headers=auth_headers(token),
        data={"name": "Dummy regressor"},
        files={
            "file": (
                "dummy.joblib",
                model_path.read_bytes(),
                "application/octet-stream",
            ),
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["metadata"]["uploaded_filename"] == "dummy.joblib"
    assert payload["metadata"]["model_type"] == "sklearn.dummy.DummyRegressor"


def test_upload_rejects_unsupported_file_extension(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    response = client.post(
        "/api/v1/models",
        headers=auth_headers(token),
        data={"name": "Bad model"},
        files={"file": ("model.txt", b"not a model", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_model_file"


def test_upload_rejects_file_without_predict_method(client: TestClient, tmp_path: Path) -> None:
    register_user(client)
    token = login_user(client)

    response = client.post(
        "/api/v1/models",
        headers=auth_headers(token),
        data={"name": "No predict"},
        files={
            "file": (
                "not-a-model.pkl",
                serialize_model({"predict": "not callable"}),
                "application/octet-stream",
            ),
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_model_file"
    assert list((tmp_path / "models" / "1").glob("*")) == []


def test_upload_rejects_invalid_metadata_json(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    response = client.post(
        "/api/v1/models",
        headers=auth_headers(token),
        data={"name": "Bad metadata", "metadata_json": "not-json"},
        files={
            "file": (
                "tiny.pkl",
                serialize_model(TinyEstimator()),
                "application/octet-stream",
            ),
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_upload_rejects_too_large_file(
    db_session: Session,
    tmp_path: Path,
) -> None:
    settings = Settings(
        app_env="test",
        jwt_secret_key="test-secret-with-at-least-thirty-two-bytes",
        model_storage_path=str(tmp_path / "models"),
        max_model_upload_size_bytes=8,
    )
    app = create_app(settings)

    def override_db_session() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        register_user(client)
        token = login_user(client)

        response = client.post(
            "/api/v1/models",
            headers=auth_headers(token),
            data={"name": "Too large"},
            files={
                "file": (
                    "large.pkl",
                    serialize_model(TinyEstimator()),
                    "application/octet-stream",
                ),
            },
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "model_file_too_large"
