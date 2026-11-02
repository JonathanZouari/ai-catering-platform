import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings

# shortcut: local SQLite file when DATABASE_URL is unset; set DATABASE_URL to Supabase for prod.
DEFAULT_SQLITE_URL = f"sqlite:///{Path(__file__).resolve().parents[2] / 'yummai.db'}"

url = get_settings().database_url or DEFAULT_SQLITE_URL
# FastAPI runs sync routes in a threadpool; SQLite must allow cross-thread use.
connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
engine = create_engine(url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
    # SQLite ignores foreign keys unless this is switched on per connection.
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
