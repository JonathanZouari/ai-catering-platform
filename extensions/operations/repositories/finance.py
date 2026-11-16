"""Income receipts and refunds. Amounts cross this boundary as Decimal, never float."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.db.money import from_minor, to_minor
from app.db.timestamps import format_utc


@dataclass(frozen=True)
class OrderBalance:
    order_id: int
    currency: str
    total: Decimal | None
    received: Decimal
    refunded: Decimal
    net_paid: Decimal
    balance_due: Decimal | None


def record_receipt(
    conn: sqlite3.Connection,
    *,
    order_id: int,
    amount: Decimal | str,
    method: str,
    occurred_at: datetime,
    document_number: str | None = None,
    recorded_by_employee_id: int | None = None,
) -> int:
    row = conn.execute("SELECT currency FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        raise LookupError(f"order {order_id} not found")
    cur = conn.execute(
        """INSERT INTO payments (kind, order_id, currency, amount_minor, method, document_number,
                                 recorded_by_employee_id, occurred_at)
           VALUES ('receipt', ?, ?, ?, ?, ?, ?, ?)""",
        (
            order_id,
            row["currency"],
            to_minor(amount),
            method,
            document_number,
            recorded_by_employee_id,
            format_utc(occurred_at),
        ),
    )
    return int(cur.lastrowid)


def record_refund(
    conn: sqlite3.Connection,
    *,
    receipt_id: int,
    amount: Decimal | str,
    method: str,
    reason: str,
    occurred_at: datetime,
    document_number: str | None = None,
    recorded_by_employee_id: int | None = None,
) -> int:
    """Refund part or all of a receipt. The database rejects refunds above the receipt."""
    row = conn.execute(
        "SELECT order_id, currency FROM payments WHERE id = ?", (receipt_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"payment {receipt_id} not found")
    cur = conn.execute(
        """INSERT INTO payments (kind, order_id, currency, amount_minor, method, document_number,
                                 refund_of_payment_id, reason, recorded_by_employee_id, occurred_at)
           VALUES ('refund', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            row["order_id"],
            row["currency"],
            to_minor(amount),
            method,
            document_number,
            receipt_id,
            reason,
            recorded_by_employee_id,
            format_utc(occurred_at),
        ),
    )
    return int(cur.lastrowid)


def order_balance(conn: sqlite3.Connection, order_id: int) -> OrderBalance:
    row = conn.execute(
        "SELECT * FROM order_payment_summary WHERE order_id = ?", (order_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"order {order_id} not found")

    def opt(value: int | None) -> Decimal | None:
        return None if value is None else from_minor(value)

    return OrderBalance(
        order_id=row["order_id"],
        currency=row["currency"],
        total=opt(row["total_minor"]),
        received=from_minor(row["received_minor"]),
        refunded=from_minor(row["refunded_minor"]),
        net_paid=from_minor(row["net_paid_minor"]),
        balance_due=opt(row["balance_due_minor"]),
    )
