"""SQLite access for local development (stdlib sqlite3, no ORM)."""

import sqlite3
from pathlib import Path

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATABASE_DIR = BACKEND_DIR.parent / "database"
MIGRATIONS_DIR = DATABASE_DIR / "migrations"
SEED_FILE = DATABASE_DIR / "seed_sqlite.sql"


def db_path() -> Path:
    path = Path(get_settings().sqlite_path)
    return path if path.is_absolute() else BACKEND_DIR / path


def get_connection(path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection with the settings every caller needs (foreign keys are off by default)."""
    target = str(path) if path is not None else str(db_path())
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if target != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection, *, seed: bool = True) -> None:
    """Apply every SQLite migration in order, then the sample seed. Safe to run repeatedly."""
    for migration in sorted(MIGRATIONS_DIR.glob("*_sqlite.sql")):
        conn.executescript(migration.read_text(encoding="utf-8"))
    if seed and SEED_FILE.exists():
        conn.executescript(SEED_FILE.read_text(encoding="utf-8"))
    conn.commit()
