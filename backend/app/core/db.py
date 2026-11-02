from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

from app.core.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "database" / "migrations"
# Long enough to queue behind other writers instead of failing during a busy moment.
LOCK_WAIT_SECONDS = 30
READ_ONLY = "yummai_read_only"


def build_engine(url: str) -> Engine:
    if not url.startswith("sqlite:///"):
        raise RuntimeError("DATABASE_URL must be a SQLite file: sqlite:///path/to/file.db")
    engine = create_engine(
        url,
        pool_pre_ping=True,
        # A request's session can move between threads; only one uses it at a time.
        connect_args={"timeout": LOCK_WAIT_SECONDS, "check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def configure(connection, _record) -> None:
        # Hands transaction control to the "begin" hook below.
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute("pragma foreign_keys = on")  # Off by default in SQLite.
        cursor.execute("pragma journal_mode = wal")  # Readers don't wait for the writer.
        cursor.execute("pragma synchronous = normal")
        cursor.close()

    @event.listens_for(engine, "begin")
    def begin(connection) -> None:
        # Writers queue here for the database's one write lock and hold it until they commit.
        # This is what replaces row locks: a transaction that checks and then writes can't be
        # overtaken. So nothing slow may run inside one, such as a call to the AI or an email.
        read_only = connection.get_execution_options().get(READ_ONLY, False)
        connection.exec_driver_sql("begin" if read_only else "begin immediate")

    return engine


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return build_engine(url)


def read_only(engine: Engine) -> Engine:
    """Reads a consistent snapshot without taking the write lock."""
    return engine.execution_options(**{READ_ONLY: True})


def apply_migrations(engine: Engine) -> list[str]:
    """Runs each new file once, in filename order, and returns the names applied."""
    connection = engine.raw_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "create table if not exists schema_migrations ("
            "name text primary key,"
            "applied_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now'))"
            ") strict"
        )
        done = {row[0] for row in cursor.execute("select name from schema_migrations").fetchall()}
        applied = []
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migration.name in done:
                continue
            script = migration.read_text(encoding="utf-8")
            try:
                cursor.executescript(
                    f"begin immediate;\n{script}\n"
                    f"insert into schema_migrations (name) values ('{migration.name}');\ncommit;"
                )
            except Exception:
                connection.rollback()
                raise
            applied.append(migration.name)
        return applied
    finally:
        connection.close()


def get_session(request: Request) -> Iterator[Session]:
    """Request-scoped session. Callers commit explicitly, so errors reach the response."""
    engine = get_engine()
    if request.method in ("GET", "HEAD"):
        engine = read_only(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
