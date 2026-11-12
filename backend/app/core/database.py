"""SQLAlchemy engine and session setup.

Defaults to a local SQLite file so the app runs with no external services. Set DATABASE_URL to a
Postgres URL (Supabase) to use that instead; the models use only portable column types.
"""

import os
from collections.abc import Iterable, Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, Table, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

SUPABASE_API_ROLES = ("anon", "authenticated")


class Base(DeclarativeBase):
    pass


def default_sqlite_path() -> Path:
    """Per-user data dir, outside the source tree: never committed or baked into an image."""
    data_home = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(data_home) / "ai-catering-platform" / "catering.db"


def resolve_database_url(url: str | None) -> str:
    return url or f"sqlite:///{default_sqlite_path()}"


def make_engine(url: str) -> Engine:
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        if engine.url.database:
            Path(engine.url.database).parent.mkdir(parents=True, exist_ok=True)

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


@lru_cache
def get_engine() -> Engine:
    return make_engine(resolve_database_url(get_settings().database_url))


def lockdown_statements(tables: Iterable[Table], *, revoke_api_roles: bool) -> list[str]:
    """SQL that makes tables unreachable from Supabase's Data API (fail closed).

    RLS with no policies hides every row from anon/authenticated; the backend's privileged
    connection bypasses RLS. The REVOKE is an extra layer, only valid where those roles exist.
    """
    roles = ", ".join(SUPABASE_API_ROLES)
    statements: list[str] = []
    for table in tables:
        statements.append(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY')
        if revoke_api_roles:
            statements.append(f'REVOKE ALL ON TABLE "{table.name}" FROM {roles}')
    return statements


def init_db(engine: Engine | None = None) -> None:
    """Create all tables that do not exist yet."""
    from app import models  # noqa: F401  (registers tables on Base.metadata)

    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            found = conn.execute(
                text("SELECT count(*) FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
            ).scalar_one()
            for statement in lockdown_statements(
                Base.metadata.sorted_tables, revoke_api_roles=found == len(SUPABASE_API_ROLES)
            ):
                conn.execute(text(statement))


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with sessionmaker(get_engine(), expire_on_commit=False)() as session:
        yield session
