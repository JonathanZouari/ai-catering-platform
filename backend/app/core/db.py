import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "database" / "migrations"


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a connection with the pragmas SQLite leaves off by default."""
    conn = sqlite3.connect(path, isolation_level=None)  # explicit BEGIN/COMMIT in services
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Apply NNNN_*.sql files newer than PRAGMA user_version, each in one transaction."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(file.name.split("_")[0])
        if version <= current:
            continue
        # executescript() commits first, so wrap the script and the version bump together by hand.
        sql = file.read_text(encoding="utf-8")
        conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {version};\nCOMMIT;")
