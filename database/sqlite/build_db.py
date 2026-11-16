"""Build a SQLite database from schema.sql (and optionally seed.sql).

Usage:
    python database/sqlite/build_db.py [output_path] [--no-seed]

The output defaults to database/sqlite/catering.db. An existing file is replaced.
"""

import argparse
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(db_path: Path, seed: bool = True) -> None:
    db_path.unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript((HERE / "schema.sql").read_text(encoding="utf-8"))
        if seed:
            conn.executescript((HERE / "seed.sql").read_text(encoding="utf-8"))
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"Foreign key violations: {violations}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", nargs="?", default=HERE / "catering.db", type=Path)
    parser.add_argument("--no-seed", action="store_true", help="create the schema only")
    args = parser.parse_args()
    build(args.output, seed=not args.no_seed)
    print(f"Built {args.output}")


if __name__ == "__main__":
    main()
