"""SQLAlchemy engine/session. SQLite for local dev, PostgreSQL (+pgvector) in prod."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


_settings = get_settings()
engine = create_engine(_settings.DATABASE_URL, connect_args=_connect_args(_settings.DATABASE_URL), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models so metadata is populated, then create tables.
    from app.models import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
