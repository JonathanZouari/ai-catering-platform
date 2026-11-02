from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

# shortcut: local SQLite file when DATABASE_URL is unset; set DATABASE_URL to Supabase for prod.
DEFAULT_SQLITE_URL = f"sqlite:///{Path(__file__).resolve().parents[2] / 'yummai.db'}"

url = get_settings().database_url or DEFAULT_SQLITE_URL
# FastAPI runs sync routes in a threadpool; SQLite must allow cross-thread use.
connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
engine = create_engine(url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
