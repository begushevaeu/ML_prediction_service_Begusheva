"""Prediction lifecycle API tests."""

from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from joblib import dump
from sklearn.dummy import DummyRegressor
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.predictions.router as predictions_router
from app.billing.service import credit_user_balance
from app.core.config import Settings, get_settings
from app.db import Base
from app.db.models import BillingTransaction, CreditBalance, MLModel
from app.db.session import get_db_session
from app.main import create_app
from app.predictions.service import execute_prediction_task


@pytest.fixture
def session_factory() -> Generator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    yield testing_session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> Generator[TestClient]:
    settings = Settings(
        app_env="test",
        jwt_secret_key="test-secret-with-at-least-thirty-two-bytes",
        model_storage_path=str(tmp_path / "models"),
    )
    app = create_app(settings)

    def override_db_session() -> Generator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as test_client:
        yield test_client


def register_user(
    client: TestClient,
    email: str = "owner@example.com",
    password: str = "strong-password",
) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Project Owner",
        },
    )
    assert response.status_code == 201


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


def build_model_file(tmp_path: Path) -> Path:
    model = DummyRegressor(strategy="mean")
    model.fit([[1], [2]], [10, 20])
    path = tmp_path / "dummy.joblib"
    dump(model, path)
    return path


def upload_model(client: TestClient, token: str, tmp_path: Path) -> int:
    path = build_model_file(tmp_path)
    response = client.post(
        "/api/v1/models",
        headers=auth_headers(token),
        data={"name": "Prediction model"},
        files={
            "file": (
                "dummy.joblib",
                path.read_bytes(),
                "application/octet-stream",
            ),
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def grant_credits(
    session_factory: sessionmaker[Session],
    *,
    user_id: int = 1,
    amount_credits: int = 5,
) -> None:
    with session_factory() as session:
        credit_user_balance(
            session,
            user_id=user_id,
            amount_credits=amount_credits,
            transaction_type="adjustment",
            description="Test credits",
            idempotency_key=f"test-credit:{user_id}:{amount_credits}",
        )
        session.commit()


class FakeTask:
    def __init__(self) -> None:
        self.prediction_ids: list[int] = []

    def delay(self, prediction_id: int) -> SimpleNamespace:
        self.prediction_ids.append(prediction_id)
        return SimpleNamespace(id=f"celery-{prediction_id}")


def test_create_prediction_enqueues_task_and_worker_saves_result(
    client: TestClient,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_user(client)
    token = login_user(client)
    model_id = upload_model(client, token, tmp_path)
    grant_credits(session_factory)
    fake_task = FakeTask()
    monkeypatch.setattr(predictions_router, "run_prediction_task", fake_task)

    response = client.post(
        "/api/v1/predictions",
        headers=auth_headers(token),
        json={"model_id": model_id, "input_payload": {"rows": [[1], [2]]}},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["celery_task_id"] == f"celery-{payload['id']}"
    assert fake_task.prediction_ids == [payload["id"]]

    result = execute_prediction_task(payload["id"], session_factory=session_factory)
    assert result["status"] == "succeeded"

    detail_response = client.get(
        f"/api/v1/predictions/{payload['id']}",
        headers=auth_headers(token),
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "succeeded"
    assert detail["result_payload"] == {"predictions": [15.0, 15.0]}
    assert detail["error_message"] is None
    assert detail["started_at"] is not None
    assert detail["completed_at"] is not None

    with session_factory() as session:
        balance = session.scalar(select(CreditBalance).where(CreditBalance.user_id == 1))
        assert balance is not None
        assert balance.credits_available == 4
        debit = session.scalar(
            select(BillingTransaction).where(
                BillingTransaction.prediction_task_id == payload["id"],
                BillingTransaction.transaction_type == "prediction_debit",
            ),
        )
        assert debit is not None
        assert debit.amount_credits == 1


def test_create_prediction_rejects_missing_rows(
    client: TestClient,
    tmp_path: Path,
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
        json={"model_id": model_id, "input_payload": {}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert fake_task.prediction_ids == []


def test_create_prediction_requires_model_ownership(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_user(client, email="owner@example.com")
    owner_token = login_user(client, email="owner@example.com")
    model_id = upload_model(client, owner_token, tmp_path)
    register_user(client, email="other@example.com")
    other_token = login_user(client, email="other@example.com")
    fake_task = FakeTask()
    monkeypatch.setattr(predictions_router, "run_prediction_task", fake_task)

    response = client.post(
        "/api/v1/predictions",
        headers=auth_headers(other_token),
        json={"model_id": model_id, "input_payload": {"rows": [[1]]}},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "404"
    assert fake_task.prediction_ids == []


def test_worker_marks_prediction_failed_when_model_file_is_missing(
    client: TestClient,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_user(client)
    token = login_user(client)
    model_id = upload_model(client, token, tmp_path)
    grant_credits(session_factory, amount_credits=1)
    fake_task = FakeTask()
    monkeypatch.setattr(predictions_router, "run_prediction_task", fake_task)

    response = client.post(
        "/api/v1/predictions",
        headers=auth_headers(token),
        json={"model_id": model_id, "input_payload": {"rows": [[1]]}},
    )
    assert response.status_code == 202
    prediction_id = response.json()["id"]

    with session_factory() as session:
        model = session.get(MLModel, model_id)
        assert model is not None
        Path(model.storage_path).unlink()

    result = execute_prediction_task(prediction_id, session_factory=session_factory)
    assert result["status"] == "failed"

    detail_response = client.get(
        f"/api/v1/predictions/{prediction_id}",
        headers=auth_headers(token),
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "failed"
    assert detail["result_payload"] is None
    assert detail["error_message"]

    with session_factory() as session:
        balance = session.scalar(select(CreditBalance).where(CreditBalance.user_id == 1))
        assert balance is not None
        assert balance.credits_available == 1
        debit = session.scalar(
            select(BillingTransaction).where(
                BillingTransaction.prediction_task_id == prediction_id,
                BillingTransaction.transaction_type == "prediction_debit",
            ),
        )
        assert debit is None
