from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-password-123"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["JUDGE_RATE_PER_MINUTE"] = "1000"
os.environ["JUDGE_MAX_CONCURRENCY"] = "4"

from sqlalchemy import create_engine, delete  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.db as db_module  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    # Use a single shared in-memory SQLite database for all tests.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    db_module.engine = engine
    db_module.SessionLocal = Session
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_database():
    for table in reversed(Base.metadata.sorted_tables):
        with db_module.engine.begin() as conn:
            conn.execute(delete(table))
    yield


@pytest.fixture()
def client():
    from app.services.admin import ensure_admin
    with db_module.SessionLocal() as db:
        ensure_admin(db)
    with TestClient(app) as c:
        yield c
