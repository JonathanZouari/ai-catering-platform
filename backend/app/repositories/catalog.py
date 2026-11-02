import sqlite3


def list_categories(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT id, name FROM dish_categories ORDER BY sort_order").fetchall()


def list_available_dishes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM dishes WHERE is_available = 1 ORDER BY sort_order"
    ).fetchall()


def get_dishes(conn: sqlite3.Connection, ids: list[str]) -> list[sqlite3.Row]:
    marks = ",".join("?" * len(ids))  # only placeholders are interpolated; values stay bound
    return conn.execute(f"SELECT * FROM dishes WHERE id IN ({marks})", ids).fetchall()  # noqa: S608


def list_zones(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT city, fee_agorot FROM delivery_zones ORDER BY rowid").fetchall()


def get_zone_fee(conn: sqlite3.Connection, city: str) -> int | None:
    row = conn.execute("SELECT fee_agorot FROM delivery_zones WHERE city = ?", (city,)).fetchone()
    return row["fee_agorot"] if row else None
