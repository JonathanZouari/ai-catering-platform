"""SQLAlchemy engine and session setup.

Defaults to a local SQLite file so the app runs with no external services. Set DATABASE_URL to a
Postgres URL (Supabase) to use that instead; the models use only portable column types.
"""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[2] / "catering.db"


class Base(DeclarativeBase):
    pass


def resolve_database_url(url: str | None) -> str:
    return url or f"sqlite:///{DEFAULT_SQLITE_PATH}"


def make_engine(url: str) -> Engine:
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


@lru_cache
def get_engine() -> Engine:
    return make_engine(resolve_database_url(get_settings().database_url))


def init_db(engine: Engine | None = None) -> None:
    """Create all tables that do not exist yet."""
    from app import models  # noqa: F401  (registers tables on Base.metadata)

    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    if engine.dialect.name == "postgresql":
        # Supabase exposes public tables through its Data API. Enable RLS with no policies so
        # anon/authenticated roles see nothing; the backend's privileged connection bypasses RLS.
        with engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                conn.execute(text(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY'))


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with sessionmaker(get_engine(), expire_on_commit=False)() as session:
        yield session
