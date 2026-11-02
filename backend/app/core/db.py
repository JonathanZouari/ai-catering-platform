import threading
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import availability as _availability  # noqa: F401  registers tables on Base
from app.models import catalog as _catalog  # noqa: F401
from app.models import orders as _orders  # noqa: F401
from app.models.base import Base

_init_lock = threading.Lock()


def get_engine() -> Engine | None:
    # lru_cache alone lets parallel first requests each build the engine and race create_all.
    with _init_lock:
        return _build_engine()


@lru_cache
def _build_engine() -> Engine | None:
    url = get_settings().database_url
    if not url:
        return None
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        # shortcut: local/test SQLite builds its schema from the models; Postgres uses the
        # SQL migrations in database/migrations/. Drop once a local Postgres is standard.
        Base.metadata.create_all(engine)
    return engine


def get_db() -> Iterator[Session]:
    engine = get_engine()
    if engine is None:
        raise AppError(503, "database_unavailable", "DATABASE_URL is not configured")
    with sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
