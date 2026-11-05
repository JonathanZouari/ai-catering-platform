import pytest
from fastapi.testclient import TestClient

from app.api.dishes import get_db
from app.core.config import get_settings
from app.db import connect
from app.main import app


@pytest.fixture
def db():
    """Live Supabase connection; every test runs in a transaction that is rolled back."""
    if not get_settings().database_url:
        pytest.skip("DATABASE_URL not set")
    conn = connect()
    with conn.transaction(force_rollback=True):
        yield conn
    conn.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
