import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path: str = "catering.db") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # off by default in SQLite
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(path: str = "catering.db") -> sqlite3.Connection:
    conn = connect(path)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn
