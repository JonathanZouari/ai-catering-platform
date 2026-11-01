from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings


def build_engine(url: str) -> Engine:
    # Supabase hands out postgresql:// URLs; SQLAlchemy needs the driver named.
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url.removeprefix(prefix)
    # prepare_threshold=None: the Supabase transaction pooler can't hold prepared statements.
    return create_engine(url, pool_pre_ping=True, connect_args={"prepare_threshold": None})


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return build_engine(url)


def get_session() -> Iterator[Session]:
    """Request-scoped session. Callers commit explicitly, so errors reach the response."""
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session
