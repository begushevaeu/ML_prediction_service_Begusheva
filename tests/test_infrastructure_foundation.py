"""Infrastructure foundation tests."""

from app.core.celery_app import create_celery_app
from app.core.config import Settings
from app.worker import healthcheck


def test_settings_include_infrastructure_urls() -> None:
    settings = Settings()

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.model_storage_path.endswith("/models")


def test_celery_app_uses_redis_broker_and_backend() -> None:
    settings = Settings(redis_url="redis://redis-test:6379/5")

    celery_app = create_celery_app(settings)

    assert celery_app.conf.broker_url == "redis://redis-test:6379/5"
    assert celery_app.conf.result_backend == "redis://redis-test:6379/5"


def test_worker_healthcheck_task_payload() -> None:
    assert healthcheck() == {"status": "ok", "worker": "ready"}
