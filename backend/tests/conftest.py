from uuid import uuid4

import pytest
from sqlalchemy import event, text

from app.core.config import get_settings
from app.core.db import init_db, make_engine


@pytest.fixture
def engine():
    """A real Postgres database, isolated in a throwaway schema dropped after the test."""
    url = get_settings().database_url
    if not url:
        pytest.skip("DATABASE_URL is not set")
    schema = f"test_{uuid4().hex}"
    admin = make_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = make_engine(url)

    @event.listens_for(engine, "connect")
    def use_test_schema(dbapi_connection, _):
        dbapi_connection.autocommit = True
        dbapi_connection.execute(f'SET search_path TO "{schema}", public')
        dbapi_connection.autocommit = False

    try:
        init_db(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
