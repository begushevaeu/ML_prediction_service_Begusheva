"""Database engine and session helpers."""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def create_db_engine(settings: Settings | None = None) -> Engine:
    """Create a SQLAlchemy engine from runtime settings."""

    resolved_settings = settings or get_settings()
    return create_engine(resolved_settings.database_url, pool_pre_ping=True)


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session]:
    """Yield a request-scoped database session."""

    with SessionLocal() as session:
        yield session


__all__ = ["SessionLocal", "create_db_engine", "engine", "get_db_session"]
