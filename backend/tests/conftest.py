import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.db import get_db
from app.main import app
from app.models.base import Base

TOKEN = "test-owner-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def make_session():
    """Session factory on a fresh in-memory SQLite DB (shared with `client`)."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def client(monkeypatch, make_session):
    """App client on that DB, with the owner token configured."""
    make = make_session

    def override():
        with make() as session:
            yield session

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(get_settings(), "admin_token", TOKEN)
    yield TestClient(app)
    app.dependency_overrides.clear()
