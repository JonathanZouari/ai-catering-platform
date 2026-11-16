"""Equipment and ingredient stock, read from the ledger views."""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

from app.db.timestamps import format_utc


class InsufficientStock(Exception):
    pass


@dataclass(frozen=True)
class BatchDraw:
    batch_id: int
    quantity: int


def equipment_stock(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM equipment_stock ORDER BY category, name COLLATE NOCASE"
    ).fetchall()


def expiring_batches(conn: sqlite3.Connection, on_or_before: date) -> list[sqlite3.Row]:
    """Batches that still hold stock and expire on or before the given date (soonest first)."""
    return conn.execute(
        """SELECT * FROM ingredient_batch_stock
           WHERE on_hand > 0 AND expires_on IS NOT NULL AND expires_on <= ?
           ORDER BY expires_on, batch_id""",
        (on_or_before.isoformat(),),
    ).fetchall()


def consume_ingredient(
    conn: sqlite3.Connection,
    *,
    ingredient_id: int,
    quantity: int,
    occurred_at: datetime,
    order_id: int | None = None,
    employee_id: int | None = None,
) -> list[BatchDraw]:
    """Consume ``quantity`` base units, first-expired-first-out, skipping expired batches.

    All-or-nothing: either every draw is recorded or none is (savepoint).
    """
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("quantity must be a positive integer in the ingredient's base unit")
    stamp = format_utc(occurred_at)
    day = stamp[:10]
    batches = conn.execute(
        """SELECT batch_id, on_hand FROM ingredient_batch_stock
           WHERE ingredient_id = ? AND on_hand > 0 AND received_on <= ?
             AND (expires_on IS NULL OR expires_on >= ?)
           ORDER BY expires_on IS NULL, expires_on, received_on, batch_id""",
        (ingredient_id, day, day),
    ).fetchall()
    available = sum(b["on_hand"] for b in batches)
    if available < quantity:
        raise InsufficientStock(
            f"ingredient {ingredient_id}: need {quantity}, usable on hand {available}"
        )

    draws: list[BatchDraw] = []
    remaining = quantity
    conn.execute("SAVEPOINT consume_ingredient")
    try:
        for batch in batches:
            take = min(remaining, batch["on_hand"])
            conn.execute(
                """INSERT INTO ingredient_movements
                       (batch_id, movement_type, quantity, order_id, employee_id, occurred_at)
                   VALUES (?, 'consumption', ?, ?, ?, ?)""",
                (batch["batch_id"], take, order_id, employee_id, stamp),
            )
            draws.append(BatchDraw(batch["batch_id"], take))
            remaining -= take
            if remaining == 0:
                break
        conn.execute("RELEASE consume_ingredient")
    except BaseException:
        conn.execute("ROLLBACK TO consume_ingredient")
        conn.execute("RELEASE consume_ingredient")
        raise
    return draws
