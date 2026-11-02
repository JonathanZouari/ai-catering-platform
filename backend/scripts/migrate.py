"""Apply new files from database/migrations. Safe to run again: each file runs once.

uv run python -m scripts.migrate
"""

from app.core.config import get_settings
from app.core.db import apply_migrations, get_engine


def main() -> None:
    if not get_settings().database_url:
        print("DATABASE_URL is not set, so there is nothing to migrate.")
        return
    applied = apply_migrations(get_engine())
    print(f"Applied: {', '.join(applied)}" if applied else "The database is up to date.")


if __name__ == "__main__":
    main()
