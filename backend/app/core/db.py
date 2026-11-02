"""SQLite access: connections, SQL-file migrations, dev seeding.

Plain stdlib `sqlite3`, no ORM. Schema changes are numbered SQL files in database/migrations/.
Run from backend/:  uv run python -m app.core.db migrate | seed
"""

import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.core.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"
SEEDS_DIR = REPO_ROOT / "database" / "seeds"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "catering.db"


def db_path() -> Path:
    configured = get_settings().database_path
    # A relative DATABASE_PATH is resolved against the repo root; an absolute one is used as is.
    return REPO_ROOT / configured if configured else DEFAULT_DB_PATH


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open a connection. Autocommit mode: use `transaction()` for multi-statement writes."""
    target = str(path) if path is not None else str(db_path())
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI may run a request's dependency and endpoint on different
    # worker threads. Each connection still serves exactly one request at a time.
    conn = sqlite3.connect(target, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # off by default in SQLite
    conn.execute("PRAGMA busy_timeout = 5000")
    if target != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE takes the write lock up front. This is SQLite's replacement for
    `SELECT ... FOR UPDATE` (ADR 0002): nobody else can write between our read and our write."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def _run_script(conn: sqlite3.Connection, sql: str, version: str | None = None) -> None:
    """Run a SQL file atomically. With `version`, record it in schema_migrations in the same
    transaction. executescript() cannot take parameters, so the bookkeeping insert follows it."""
    conn.executescript("BEGIN;\n" + sql)
    try:
        if version is not None:
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply pending migrations in filename order. Returns the versions applied now."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version TEXT PRIMARY KEY,"
        " applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')))"
    )
    done = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
    applied = []
    for file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if file.stem in done:
            continue
        try:
            _run_script(conn, file.read_text(encoding="utf-8"), version=file.stem)
        except BaseException:
            if conn.in_transaction:  # executescript failed midway, leaving its BEGIN open
                conn.execute("ROLLBACK")
            raise
        applied.append(file.stem)
    return applied


def seed(conn: sqlite3.Connection) -> list[str]:
    """Load dev placeholder data. Seed files use INSERT OR IGNORE, so re-running is safe."""
    files = sorted(SEEDS_DIR.glob("*.sql"))
    for file in files:
        try:
            _run_script(conn, file.read_text(encoding="utf-8"))
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    return [f.stem for f in files]


if __name__ == "__main__":
    commands = {"migrate": migrate, "seed": seed}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit("usage: python -m app.core.db [migrate|seed]")
    with connect() as connection:
        print(
            f"{sys.argv[1]} on {db_path()}: {commands[sys.argv[1]](connection) or 'nothing to do'}"
        )
