"""Create (or update) the local SQLite database: python scripts/init_db.py  (run from backend/)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import db_path, get_connection, init_db  # noqa: E402


def main() -> None:
    with get_connection() as conn:
        init_db(conn)
        tables = ["dish_categories", "dishes", "allergens", "dish_allergens", "customers", "orders"]
        counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}  # noqa: S608
    print(f"Database ready: {db_path()}")
    for table, n in counts.items():
        print(f"  {table:16} {n}")


if __name__ == "__main__":
    main()
