import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import get_session, make_engine
from app.main import app
from app.seed import seed_catalog


@pytest.fixture
def engine(tmp_path):
    """A seeded throwaway SQLite file, so tests never reach the DATABASE_URL in .env."""
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    seed_catalog(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine):
    def _session():
        with sessionmaker(engine)() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()
