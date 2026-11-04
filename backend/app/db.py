"""Local SQLite database (lesson 15 homework).

The schema lives in database/schema.sql. The database file itself is created on
each machine and is git-ignored.

    cd backend
    uv run python -m app.db     # create database/catering.db and seed demo data
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = REPO_ROOT / "database"
SCHEMA_PATH = DATABASE_DIR / "schema.sql"

# Tests point this at a temporary file.
DB_PATH = DATABASE_DIR / "catering.db"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection. Rows come back as sqlite3.Row (dict-like, not plain tuples)."""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    # SQLite does not enforce FOREIGN KEY unless asked, per connection.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Create every table from database/schema.sql (idempotent)."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with closing(get_connection(db_path)) as conn:
        conn.executescript(schema)
        conn.commit()


CATEGORIES = [
    # (name, sort_order)
    ("ראשונות", 1),
    ("עיקריות", 2),
    ("קינוחים", 3),
]

ALLERGENS = ["גלוטן", "אגוזים", "חלב", "ביצים", "שומשום", "סויה", "דגים"]

DISHES = [
    # (category, name, description, pricing_unit, unit_price, kashrut, vegetarian, vegan)
    ("ראשונות", "חומוס ביתי", "עם טחינה, שמן זית ופפריקה", "per_tray", 60.0, "pareve", 1, 1),
    ("ראשונות", "סלט ירקות קצוץ", "עגבנייה, מלפפון ובצל", "per_guest", 12.0, "pareve", 1, 1),
    ("ראשונות", "פשטידת ירק", "קישואים, גזר וגבינה", "per_tray", 85.0, "dairy", 1, 0),
    ("עיקריות", "פרגית בגריל", "במרינדה של לימון ושום", "per_guest", 48.0, "meat", 0, 0),
    ("עיקריות", "סלמון אפוי", "עם עשבי תיבול", "per_guest", 65.0, "pareve", 0, 0),
    ("עיקריות", "מג'דרה", "אורז, עדשים ובצל מטוגן", "per_tray", 70.0, "pareve", 1, 1),
    ("קינוחים", "מלבי", "עם פיסטוק ומי ורדים", "per_item", 14.0, "dairy", 1, 0),
    ("קינוחים", "עוגת שוקולד", "עוגה שלמה, 12 פרוסות", "per_item", 90.0, "dairy", 1, None),
]

DISH_ALLERGENS = [
    # (dish, allergen, status). No row = unknown.
    ("חומוס ביתי", "שומשום", "contains"),
    ("חומוס ביתי", "גלוטן", "free"),
    ("סלט ירקות קצוץ", "גלוטן", "free"),
    ("פשטידת ירק", "גלוטן", "contains"),
    ("פשטידת ירק", "ביצים", "contains"),
    ("פשטידת ירק", "חלב", "contains"),
    ("פרגית בגריל", "גלוטן", "free"),
    ("סלמון אפוי", "דגים", "contains"),
    ("סלמון אפוי", "גלוטן", "free"),
    ("מג'דרה", "גלוטן", "free"),
    ("מלבי", "חלב", "contains"),
    ("מלבי", "אגוזים", "contains"),
    ("עוגת שוקולד", "גלוטן", "contains"),
    ("עוגת שוקולד", "ביצים", "contains"),
    ("עוגת שוקולד", "חלב", "contains"),
]

DEMO_ORDER_ITEMS = [
    # (dish, quantity)
    ("סלט ירקות קצוץ", 25),
    ("פרגית בגריל", 20),
    ("מג'דרה", 3),
    ("מלבי", 25),
]
DEMO_DELIVERY_FEE = 80.0


def seed_db(db_path: Path | None = None) -> bool:
    """Insert demo data. Returns False (and does nothing) if the menu is already seeded."""
    with closing(get_connection(db_path)) as conn:
        cursor = conn.cursor()
        if cursor.execute("SELECT COUNT(*) FROM dish_categories").fetchone()[0]:
            return False

        cursor.executemany(
            "INSERT INTO dish_categories (name, sort_order) VALUES (?, ?)", CATEGORIES
        )
        cursor.executemany("INSERT INTO allergens (name) VALUES (?)", [(a,) for a in ALLERGENS])

        category_ids = {
            row["name"]: row["id"]
            for row in cursor.execute("SELECT id, name FROM dish_categories").fetchall()
        }
        allergen_ids = {
            row["name"]: row["id"]
            for row in cursor.execute("SELECT id, name FROM allergens").fetchall()
        }

        dish_ids: dict[str, int] = {}
        dish_prices: dict[str, float] = {}
        for category, name, description, unit, price, kashrut, veg, vegan in DISHES:
            cursor.execute(
                """
                INSERT INTO dishes
                    (category_id, name, description, pricing_unit, unit_price,
                     kashrut, is_vegetarian, is_vegan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (category_ids[category], name, description, unit, price, kashrut, veg, vegan),
            )
            dish_ids[name] = cursor.lastrowid
            dish_prices[name] = price

        cursor.executemany(
            "INSERT INTO dish_allergens (dish_id, allergen_id, status) VALUES (?, ?, ?)",
            [(dish_ids[d], allergen_ids[a], status) for d, a, status in DISH_ALLERGENS],
        )

        # One demo customer with one event and one submitted order.
        cursor.execute(
            "INSERT INTO customers (full_name, phone, email) VALUES (?, ?, ?)",
            ("דנה לוי", "050-1234567", "dana@example.com"),
        )
        customer_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO events
                (customer_id, event_type, event_date, adults, children,
                 vegetarian_guests, vegan_guests, dietary_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (customer_id, "יום הולדת", "2026-11-20", 20, 5, 3, 1, "אחת האורחות אלרגית לאגוזים"),
        )
        event_id = cursor.lastrowid

        subtotal = sum(dish_prices[d] * qty for d, qty in DEMO_ORDER_ITEMS)
        cursor.execute(
            """
            INSERT INTO orders
                (customer_id, event_id, status, fulfillment_type, delivery_address,
                 subtotal, delivery_fee, total, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                event_id,
                "pending_approval",
                "delivery",
                "רחוב הרצל 10, תל אביב",
                subtotal,
                DEMO_DELIVERY_FEE,
                subtotal + DEMO_DELIVERY_FEE,
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        order_id = cursor.lastrowid
        cursor.executemany(
            """
            INSERT INTO order_items
                (order_id, dish_id, quantity, snapshot_name, snapshot_unit_price,
                 snapshot_line_total)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (order_id, dish_ids[d], qty, d, dish_prices[d], dish_prices[d] * qty)
                for d, qty in DEMO_ORDER_ITEMS
            ],
        )

        conn.commit()
        return True


def main() -> None:
    init_db()
    seeded = seed_db()
    print(f"database ready: {DB_PATH}")
    print("seeded demo data" if seeded else "already seeded, nothing added")


if __name__ == "__main__":
    main()
