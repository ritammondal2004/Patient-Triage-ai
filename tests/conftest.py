"""Shared fixtures for the test suite."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app


# In-memory SQLite for test isolation — no Neon dependency needed.
TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=TEST_ENGINE, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Create all tables once per test session."""
    from app.models import orm  # noqa: F401

    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture()
def db():
    """Yield a fresh DB session that rolls back after every test."""
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(db):
    """FastAPI TestClient wired to the test database."""

    def _override_db():
        try:
            yield db
        finally:
            pass  # db fixture handles cleanup

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()
