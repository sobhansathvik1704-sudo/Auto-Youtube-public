"""Pytest fixtures shared across all test modules."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Override settings BEFORE importing the app so that pydantic-settings picks
# up the test values instead of reading from .env.example
# ---------------------------------------------------------------------------
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-do-not-use-in-production")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
os.environ.setdefault("LLM_PROVIDER", "local")
os.environ.setdefault("TTS_PROVIDER", "local")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DEBUG", "false")

from app.core.database import Base  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402

# Import all models so SQLAlchemy registers their tables with Base.metadata
import app.db.base  # noqa: E402, F401


@pytest.fixture()
def engine(tmp_path):
    """Create a fresh SQLite database for each test to ensure full isolation."""
    db_path = tmp_path / "test.db"
    _engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)
    _engine.dispose()


@pytest.fixture()
def db_session(engine):
    """Provide a database session bound to the per-test SQLite engine."""
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    """FastAPI test client with the database dependency overridden."""
    from app.api.deps import get_database  # noqa: PLC0415

    def override_get_database():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_database] = override_get_database
    with TestClient(fastapi_app, raise_server_exceptions=True) as c:
        yield c
    fastapi_app.dependency_overrides.pop(get_database, None)


@pytest.fixture()
def registered_user(client):
    """Register a test user and return the token response payload."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "testuser@example.com",
            "password": "securepassword123",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def auth_headers(registered_user):
    """Return Authorization headers for the registered test user."""
    token = registered_user["access_token"]
    return {"Authorization": f"Bearer {token}"}
