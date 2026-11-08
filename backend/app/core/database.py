from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

# Local development falls back to a SQLite file in backend/. Supabase Postgres is used when
# DATABASE_URL is set (ADR 0002); the models stay portable between the two.
DEFAULT_DATABASE_URL = "sqlite:///./catering.db"


class Base(DeclarativeBase):
    pass


def normalize_url(url: str) -> str:
    """Supabase hands out `postgresql://` (or `postgres://`) URLs; SQLAlchemy would pick psycopg2
    for those, but the installed driver is psycopg 3."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def make_engine(url: str) -> Engine:
    engine = create_engine(normalize_url(url), pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        # SQLite ignores foreign keys unless enabled on every connection.
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()

    return engine


@lru_cache
def get_engine() -> Engine:
    return make_engine(get_settings().database_url or DEFAULT_DATABASE_URL)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with sessionmaker(get_engine())() as session:
        yield session
