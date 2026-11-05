from collections.abc import Iterator
from functools import lru_cache

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

from app.core.config import get_settings

READ_ONLY = "yummai_read_only"


def build_engine(url: str) -> Engine:
    # Supabase hands out postgresql:// URLs; SQLAlchemy needs the driver named.
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url.removeprefix(prefix)
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("DATABASE_URL must be a Postgres URL: postgresql://...")
    # prepare_threshold=None: Supabase's pooler can't always hold prepared statements.
    engine = create_engine(url, pool_pre_ping=True, connect_args={"prepare_threshold": None})

    @event.listens_for(engine, "begin")
    def begin(connection) -> None:
        # GET and HEAD must not write, so the database refuses it instead of trusting the code.
        if connection.get_execution_options().get(READ_ONLY, False):
            connection.exec_driver_sql("set transaction read only")

    return engine


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return build_engine(url)


def read_only(engine: Engine) -> Engine:
    """Every transaction on the returned engine is read-only."""
    return engine.execution_options(**{READ_ONLY: True})


def get_session(request: Request) -> Iterator[Session]:
    """Request-scoped session. Callers commit explicitly, so errors reach the response.

    Writes that check and then change a row take row locks (OrderRepository.lock), so slow
    work such as AI calls, emails or uploads must run after the commit, not inside it.
    """
    engine = get_engine()
    if request.method in ("GET", "HEAD"):
        engine = read_only(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
