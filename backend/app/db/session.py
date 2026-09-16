"""SQLAlchemy engine/session. SQLite for local dev, PostgreSQL (+pgvector) in prod."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

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
    _ensure_v02_columns()


def _ensure_v02_columns() -> None:
    """Additive upgrade for pre-v0.2 dev databases (create_all never alters tables).

    New Postgres deployments should apply database/migrations/003_v02.sql and 004_v03.sql instead.
    """
    import sqlalchemy as sa

    adds: dict[str, list[tuple[str, str]]] = {
        "research_runs": [
            ("mode", "VARCHAR(20) DEFAULT 'web'"),
            ("stop_reason", "TEXT"),
            ("stage_ms", "JSON"),
            ("llm_calls", "INTEGER DEFAULT 0"),
            ("input_tokens", "INTEGER DEFAULT 0"),
            ("output_tokens", "INTEGER DEFAULT 0"),
            ("embedding_calls", "INTEGER DEFAULT 0"),
            ("search_calls", "INTEGER DEFAULT 0"),
            ("estimated_cost_usd", "FLOAT DEFAULT 0"),
        ],
        "sources": [
            ("origin", "VARCHAR(20) DEFAULT 'web'"),
            ("canonical_url", "TEXT"),
            ("discovered_by", "JSON"),
            ("ranking_reasons", "JSON"),
        ],
        "claims": [
            ("sub_question", "TEXT"),
            ("agreement", "JSON"),
        ],
        "reports": [
            ("research_method", "TEXT DEFAULT ''"),
        ],
        "documents": [
            ("version", "INTEGER DEFAULT 1"),
            ("first_seen", "TIMESTAMP"),
            ("last_seen", "TIMESTAMP"),
            ("embedding_model", "VARCHAR(100)"),
            ("embedding_dim", "INTEGER"),
        ],
    }
    with engine.begin() as conn:
        for table, cols in adds.items():
            try:
                existing = {r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            except Exception:
                try:
                    existing = {c["name"] for c in sa.inspect(conn).get_columns(table)}
                except Exception:
                    continue
            for name, ddl in cols:
                if name not in existing:
                    # JSON type works on SQLite (stored as TEXT) and Postgres (JSON).
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

    # Ensure retrieval_error table exists (create_all handles new tables, but guard for old DBs)
    try:
        with engine.begin() as conn:
            existing_tables = {r[0] for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
    except Exception:
        existing_tables = set()
    if "retrieval_error" not in existing_tables:
        with engine.begin() as conn:
            conn.exec_driver_sql("""
                CREATE TABLE retrieval_error (
                    id VARCHAR(36) PRIMARY KEY,
                    run_id VARCHAR(36) NOT NULL,
                    question_id VARCHAR(36) NOT NULL,
                    query TEXT NOT NULL,
                    error_type VARCHAR(50) NOT NULL,
                    source_id VARCHAR(36),
                    chunk_id VARCHAR(36),
                    expected TEXT,
                    actual TEXT,
                    severity VARCHAR(20) DEFAULT 'medium',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.exec_driver_sql("CREATE INDEX ix_retrieval_error_run ON retrieval_error(run_id)")
            conn.exec_driver_sql("CREATE INDEX ix_retrieval_error_type ON retrieval_error(error_type)")
