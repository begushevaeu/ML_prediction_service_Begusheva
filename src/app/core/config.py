"""Application configuration helpers."""

import os
from dataclasses import dataclass
from functools import lru_cache

ALLOWED_JWT_ALGORITHMS = {"HS256"}
DEFAULT_JWT_SECRET_KEY = "change-me-to-a-long-random-secret-key"
LOCAL_APP_ENVS = {"dev", "development", "local", "test"}


def _read_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return int(raw_value)


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    app_name: str = "ML Prediction Service"
    app_env: str = "local"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://ml_user:change-me@postgres:5432/ml_prediction_service"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret_key: str = DEFAULT_JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    model_storage_path: str = "/var/lib/ml_prediction_service/models"
    max_model_upload_size_bytes: int = 10 * 1024 * 1024
    prediction_price_credits: int = 1
    celery_task_queue: str = "celery"
    bootstrap_local_admin: bool = False
    local_admin_username: str = "admin"
    local_admin_email: str = "admin@example.com"
    local_admin_password: str = "admin"


def validate_security_settings(settings: Settings) -> None:
    """Fail fast when runtime settings are unsafe outside local/test use."""

    if settings.jwt_algorithm not in ALLOWED_JWT_ALGORITHMS:
        raise RuntimeError("JWT_ALGORITHM must be HS256")

    if settings.access_token_expire_minutes <= 0:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")

    if settings.max_model_upload_size_bytes <= 0:
        raise RuntimeError("MAX_MODEL_UPLOAD_SIZE_BYTES must be positive")

    if settings.prediction_price_credits <= 0:
        raise RuntimeError("PREDICTION_PRICE_CREDITS must be positive")

    if settings.bootstrap_local_admin and settings.app_env.strip().lower() not in {
        "local",
        "dev",
        "development",
    }:
        raise RuntimeError("BOOTSTRAP_LOCAL_ADMIN can only be enabled locally")

    if settings.app_env.strip().lower() in LOCAL_APP_ENVS:
        return

    if settings.app_debug:
        raise RuntimeError("APP_DEBUG must be disabled outside local/test environments")

    if settings.jwt_secret_key == DEFAULT_JWT_SECRET_KEY or len(settings.jwt_secret_key) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be changed to a random secret with at least 32 characters",
        )


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process."""

    return Settings(
        app_name=os.getenv("APP_NAME", Settings.app_name),
        app_env=os.getenv("APP_ENV", Settings.app_env),
        app_debug=_read_bool("APP_DEBUG", Settings.app_debug),
        api_v1_prefix=os.getenv("API_V1_PREFIX", Settings.api_v1_prefix),
        database_url=os.getenv("DATABASE_URL", Settings.database_url),
        redis_url=os.getenv("REDIS_URL", Settings.redis_url),
        jwt_secret_key=os.getenv("JWT_SECRET_KEY", Settings.jwt_secret_key),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", Settings.jwt_algorithm),
        access_token_expire_minutes=_read_int(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            Settings.access_token_expire_minutes,
        ),
        model_storage_path=os.getenv("MODEL_STORAGE_PATH", Settings.model_storage_path),
        max_model_upload_size_bytes=_read_int(
            "MAX_MODEL_UPLOAD_SIZE_BYTES",
            Settings.max_model_upload_size_bytes,
        ),
        prediction_price_credits=_read_int(
            "PREDICTION_PRICE_CREDITS",
            Settings.prediction_price_credits,
        ),
        celery_task_queue=os.getenv("CELERY_TASK_QUEUE", Settings.celery_task_queue),
        bootstrap_local_admin=_read_bool(
            "BOOTSTRAP_LOCAL_ADMIN",
            Settings.bootstrap_local_admin,
        ),
        local_admin_username=os.getenv("LOCAL_ADMIN_USERNAME", Settings.local_admin_username),
        local_admin_email=os.getenv("LOCAL_ADMIN_EMAIL", Settings.local_admin_email),
        local_admin_password=os.getenv("LOCAL_ADMIN_PASSWORD", Settings.local_admin_password),
    )


__all__ = [
    "ALLOWED_JWT_ALGORITHMS",
    "DEFAULT_JWT_SECRET_KEY",
    "LOCAL_APP_ENVS",
    "Settings",
    "get_settings",
    "validate_security_settings",
]
