"""Apply database/migrations/*.sql to Postgres in name order, each once (Railway pre-deploy).

Usage, from backend/:  python -m app.core.migrate [--dry-run]
Applied files are recorded in schema_migrations; each file runs in its own transaction, so a
failing one leaves the database as it was before that file and stops the deploy.
"""

import sys
from pathlib import Path

import psycopg

from app.core.config import get_settings

MIGRATIONS = Path(__file__).resolve().parents[3] / "database" / "migrations"
LOCK_ID = 7_274_001  # advisory lock: two deploys never migrate at once


def migrate(url: str, dry_run: bool = False) -> list[str]:
    """Apply the pending migrations; returns their file names."""
    url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, autocommit=True, prepare_threshold=None) as conn:
        conn.execute("select pg_advisory_lock(%s)", (LOCK_ID,))
        conn.execute(
            "create table if not exists schema_migrations "
            "(name text primary key, applied_at timestamptz not null default now())"
        )
        done = {row[0] for row in conn.execute("select name from schema_migrations")}
        todo = [p for p in sorted(MIGRATIONS.glob("*.sql")) if p.name not in done]
        for path in [] if dry_run else todo:
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))  # no params: runs as a script
                conn.execute("insert into schema_migrations (name) values (%s)", (path.name,))
        return [p.name for p in todo]


def main() -> None:
    url = get_settings().database_url
    if not url or not url.startswith(("postgres://", "postgresql")):
        sys.exit("DATABASE_URL is not a Postgres URL; nothing to migrate")
    dry_run = "--dry-run" in sys.argv
    names = migrate(url, dry_run)
    verb = "pending" if dry_run else "applied"
    print(f"{len(names)} migration(s) {verb}: {', '.join(names) or '-'}")  # never print the URL


if __name__ == "__main__":
    main()
