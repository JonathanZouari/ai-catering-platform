"""Forward-only, non-destructive SQL migrations.

Each ``NNNN_name.sql`` file in ``database/migrations`` is applied once, in order, inside its own
transaction, and recorded in ``schema_migrations`` with a checksum. Running ``migrate`` again only
applies files that are new; it never drops or rewrites existing data. A changed checksum or an
applied version that no longer exists on disk stops the run instead of guessing.
"""

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.db.connection import connect

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "database" / "migrations"
FILENAME_RE = re.compile(r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.sql$")

_LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT
"""


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    sql: str
    checksum: str


def _read(path: Path) -> tuple[str, str]:
    # Normalise line endings so a Windows checkout (CRLF) has the same checksum as Linux CI.
    text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations: dict[str, Migration] = {}
    for path in sorted(directory.glob("*.sql")):
        match = FILENAME_RE.match(path.name)
        if not match:
            raise MigrationError(f"migration file name must look like 0001_name.sql: {path.name}")
        version = match["version"]
        if version in migrations:
            raise MigrationError(f"duplicate migration version {version}")
        sql, checksum = _read(path)
        migrations[version] = Migration(version, match["name"], sql, checksum)
    return [migrations[v] for v in sorted(migrations)]


def migrate(db_path: str | Path, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations. Returns the versions applied by this call (empty if none)."""
    available = discover(directory)
    known = {m.version for m in available}
    applied_now: list[str] = []

    conn = connect(db_path, autocommit=True)
    try:
        conn.execute(_LEDGER_DDL)
        unknown = sorted(
            row[0]
            for row in conn.execute("SELECT version FROM schema_migrations")
            if row[0] not in known
        )
        if unknown:
            raise MigrationError(
                f"database has migrations this code does not know about: {', '.join(unknown)}"
            )

        for migration in available:
            # IMMEDIATE takes the write lock up front, so two processes starting together
            # cannot both apply the same migration.
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT checksum FROM schema_migrations WHERE version = ?",
                    (migration.version,),
                ).fetchone()
                if row is not None:
                    if row[0] != migration.checksum:
                        raise MigrationError(
                            f"migration {migration.version}_{migration.name} was edited after it "
                            "was applied; add a new migration instead"
                        )
                    conn.execute("COMMIT")
                    continue

                conn.executescript(migration.sql)
                if not conn.in_transaction:
                    raise MigrationError(
                        f"migration {migration.version} ended the transaction; remove "
                        "BEGIN/COMMIT from the file"
                    )
                violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise MigrationError(
                        f"migration {migration.version} left {len(violations)} foreign key "
                        "violation(s)"
                    )
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, checksum) VALUES (?, ?, ?)",
                    (migration.version, migration.name, migration.checksum),
                )
                conn.execute("COMMIT")
                applied_now.append(migration.version)
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
    except sqlite3.Error as exc:
        raise MigrationError(f"migration failed: {exc}") from exc
    finally:
        conn.close()
    return applied_now


def applied_versions(conn: sqlite3.Connection) -> list[str]:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if not exists:
        return []
    return [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY 1")]
