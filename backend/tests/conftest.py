import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("SEARCH_PROVIDER", "mock")


@pytest.fixture()
def db():
    from app.db.session import Base
    from app.models import db_models  # noqa: F401
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    # Patch global engine so app lifespan uses same in-memory DB
    import app.db.session as session_module
    orig_engine = session_module.engine
    orig_sl = session_module.SessionLocal
    session_module.engine = engine
    session_module.SessionLocal = TestingSession
    s = TestingSession()
    try:
        yield s
    finally:
        s.close()
        session_module.engine = orig_engine
        session_module.SessionLocal = orig_sl
