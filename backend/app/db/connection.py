import sqlite3
from collections.abc import Iterator
from pathlib import Path

from app.core.config import get_settings

# STRICT tables need SQLite 3.37+.
MIN_SQLITE_VERSION = (3, 37, 0)
BUSY_TIMEOUT_MS = 5000


def _is_file_database(target: str) -> bool:
    return target != ":memory:" and not target.startswith("file:")


def connect(path: str | Path, *, autocommit: bool = False) -> sqlite3.Connection:
    """Open a connection with foreign keys enforced.

    Every connection in the app must come from here: SQLite keeps foreign keys off unless each
    connection turns them on, and the pragma is ignored inside a transaction. So the pragmas run
    in autocommit mode first, and only then does the connection switch to PEP 249 transactions
    (unless ``autocommit=True`` is requested, as the migration runner does).
    """
    if sqlite3.sqlite_version_info < MIN_SQLITE_VERSION:
        raise RuntimeError(
            f"SQLite {'.'.join(map(str, MIN_SQLITE_VERSION))}+ is required, "
            f"found {sqlite3.sqlite_version}"
        )
    target = str(path)
    if _is_file_database(target):
        Path(target).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        target,
        autocommit=True,
        timeout=BUSY_TIMEOUT_MS / 1000,
        # FastAPI may open and close one request's connection on different threads.
        check_same_thread=False,
        uri=target.startswith("file:"),
    )
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        if _is_file_database(target):
            conn.execute("PRAGMA journal_mode = WAL")
        if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("SQLite foreign key enforcement could not be enabled")
        conn.autocommit = autocommit
    except BaseException:
        conn.close()
        raise
    return conn


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request; commits on success, rolls back on error."""
    conn = connect(get_settings().sqlite_file)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
