"""Application configuration helpers."""

import os
from dataclasses import dataclass
from functools import lru_cache


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
    jwt_secret_key: str = "change-me-to-a-long-random-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    model_storage_path: str = "/var/lib/ml_prediction_service/models"
    prediction_price_credits: int = 1


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
        prediction_price_credits=_read_int(
            "PREDICTION_PRICE_CREDITS",
            Settings.prediction_price_credits,
        ),
    )
