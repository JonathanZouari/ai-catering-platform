"""Copy the live database to one file, safely while the app is running.

    uv run python -m scripts.backup_database /data/backups/yummai-2026-11-02.db

The file holds customers' personal details. Keep it private and never commit it.
"""

import argparse
from pathlib import Path

from app.core.db import get_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy the live database to a new file.")
    parser.add_argument("target", type=Path)
    target = parser.parse_args().target
    target.parent.mkdir(parents=True, exist_ok=True)
    # Outside any transaction, which VACUUM requires.
    connection = get_engine().raw_connection()
    try:
        connection.cursor().execute("vacuum into ?", (str(target),))
    finally:
        connection.close()
    print(f"Saved {target}")


if __name__ == "__main__":
    main()
