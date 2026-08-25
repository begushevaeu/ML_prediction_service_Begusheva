"""Application configuration helpers."""

import os
from dataclasses import dataclass
from functools import lru_cache


def _read_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    app_name: str = "ML Prediction Service"
    app_env: str = "local"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process."""

    return Settings(
        app_name=os.getenv("APP_NAME", Settings.app_name),
        app_env=os.getenv("APP_ENV", Settings.app_env),
        app_debug=_read_bool("APP_DEBUG", Settings.app_debug),
        api_v1_prefix=os.getenv("API_V1_PREFIX", Settings.api_v1_prefix),
    )
