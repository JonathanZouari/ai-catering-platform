import sqlite3
from collections.abc import Iterator
from pathlib import Path

from app.core.config import get_settings

DATABASE_DIR = Path(__file__).resolve().parents[3] / "database"
MIGRATIONS_DIR = DATABASE_DIR / "migrations"
SEEDS_DIR = DATABASE_DIR / "seeds"


def connect(path: Path) -> sqlite3.Connection:
    # One connection per request, so it is safe to use from FastAPI's worker threads.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path) -> None:
    """Create the database file if needed and apply every migration and seed not applied yet.

    Each SQL file runs once, in name order, inside its own transaction.
    Seeds hold sample data and run after all migrations.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "name TEXT PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')))"
        )
        conn.commit()
        applied = {row["name"] for row in conn.execute("SELECT name FROM schema_migrations")}
        files = [*sorted(MIGRATIONS_DIR.glob("*.sql")), *sorted(SEEDS_DIR.glob("*.sql"))]
        for file in files:
            name = f"{file.parent.name}/{file.name}"
            if name not in applied:
                _apply(conn, name, file.read_text(encoding="utf-8"))
    finally:
        conn.close()


def _apply(conn: sqlite3.Connection, name: str, sql: str) -> None:
    try:
        # executescript cannot bind parameters, so the file and its record are two calls
        # inside one explicit transaction: a failing file leaves no tables and no record.
        conn.executescript(f"BEGIN;\n{sql}")
        conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (name,))
        conn.execute("COMMIT")
    except sqlite3.Error:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: a connection for the current request."""
    conn = connect(get_settings().sqlite_path)
    try:
        yield conn
    finally:
        conn.close()
