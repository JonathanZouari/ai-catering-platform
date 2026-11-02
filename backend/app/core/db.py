import sqlite3
from collections.abc import Iterator
from pathlib import Path

from app.core.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "database" / "migrations"


def connect() -> sqlite3.Connection:
    # check_same_thread=False: sync dependencies and endpoints may run on different threads.
    conn = sqlite3.connect(get_settings().sqlite_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            conn.executescript(path.read_text(encoding="utf-8"))
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
