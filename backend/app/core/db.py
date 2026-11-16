from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, text

from app.core.config import get_settings

DATABASE_DIR = Path(__file__).resolve().parents[3] / "database"
MIGRATIONS_DIR = DATABASE_DIR / "migrations"
SEEDS_DIR = DATABASE_DIR / "seeds"
MIGRATION_LOCK_KEY = 20261105


def make_engine(url: str) -> Engine:
    # Supabase hands out postgresql:// URLs, which SQLAlchemy would send to psycopg2.
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    # max_overflow=0 keeps the app inside the small connection limit of Supabase's shared pooler.
    return create_engine(url, pool_size=5, max_overflow=0, pool_pre_ping=True)


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set. See .env.example.")
    return make_engine(url)


def init_db(engine: Engine) -> None:
    """Apply every migration and seed not applied yet.

    Each SQL file runs once, in name order. Seeds hold sample data and run after all
    migrations. Everything runs in one transaction: a failing file leaves nothing behind.
    """
    files = [*sorted(MIGRATIONS_DIR.glob("*.sql")), *sorted(SEEDS_DIR.glob("*.sql"))]
    with engine.begin() as conn:
        # Two containers can start together during a deploy; only one applies files at a time.
        conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
        )
        conn.execute(text("ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY"))
        applied = set(conn.scalars(text("SELECT name FROM schema_migrations")))
        for file in files:
            name = f"{file.parent.name}/{file.name}"
            if name not in applied:
                # psycopg runs a multi-statement string only when no parameters are bound.
                conn.exec_driver_sql(
                    file.read_text(encoding="utf-8"), execution_options={"no_parameters": True}
                )
                conn.execute(
                    text("INSERT INTO schema_migrations (name) VALUES (:name)"), {"name": name}
                )


def get_db() -> Iterator[Connection]:
    """FastAPI dependency: a connection for the current request."""
    with get_engine().connect() as conn:
        yield conn
