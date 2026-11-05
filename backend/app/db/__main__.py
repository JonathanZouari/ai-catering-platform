"""Initialise or inspect the SQLite database.

uv run python -m app.db            # apply pending migrations (safe to repeat)
uv run python -m app.db status     # show applied and pending migrations
uv run python -m app.db --path /tmp/x.sqlite3
"""

import argparse
import sys
from pathlib import Path

from app.core.config import get_settings
from app.db.connection import connect
from app.db.migrations import MigrationError, applied_versions, discover, migrate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.db", description=__doc__.splitlines()[0])
    parser.add_argument("command", nargs="?", choices=("migrate", "status"), default="migrate")
    parser.add_argument("--path", help="SQLite file (default: SQLITE_PATH setting)")
    args = parser.parse_args(argv)
    path = args.path or get_settings().sqlite_file

    if args.command == "migrate":
        try:
            applied = migrate(path)
        except MigrationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"{path}: applied {', '.join(applied)}" if applied else f"{path}: up to date")
        return 0

    done: set[str] = set()
    if Path(path).exists():  # reading status must not create an empty database
        conn = connect(path)
        try:
            done = set(applied_versions(conn))
        finally:
            conn.close()
    for m in discover():
        print(f"{'applied' if m.version in done else 'pending'}  {m.version}_{m.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
