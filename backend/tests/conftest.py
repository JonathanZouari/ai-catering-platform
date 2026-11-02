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
def client(monkeypatch):
    """App client on a fresh in-memory SQLite DB, with the owner token configured."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    make = sessionmaker(engine, expire_on_commit=False)

    def override():
        with make() as session:
            yield session

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(get_settings(), "admin_token", TOKEN)
    yield TestClient(app)
    app.dependency_overrides.clear()
