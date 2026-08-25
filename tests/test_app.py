"""Foundation tests for the application package."""

from fastapi.testclient import TestClient

from app import APP_NAME
from app.core.config import Settings
from app.main import create_app


def test_app_name_constant() -> None:
    assert APP_NAME == "ML Prediction Service"


def test_root_endpoint_returns_service_metadata() -> None:
    client = TestClient(create_app(Settings(app_env="test")))

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "ML Prediction Service",
        "status": "ready",
    }


def test_health_endpoint_returns_environment() -> None:
    client = TestClient(create_app(Settings(app_env="test")))

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ML Prediction Service",
        "environment": "test",
    }
