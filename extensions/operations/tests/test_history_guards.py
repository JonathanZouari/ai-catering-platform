# ruff: noqa: S608 -- SQL identifiers come only from the fixed parametrized table list.
import json
import sqlite3

import pytest


STAMP = "2026-11-02T10:00:00Z"
WINDOW = {"window_start": "2026-12-20T14:00:00Z", "window_end": "2026-12-20T15:00:00Z"}


@pytest.mark.parametrize("table", ["payments", "equipment_movements", "ingredient_movements"])
def test_replace_cannot_rewrite_ledgers(conn, make, table):
    if table == "payments":
        row_id = make.insert(
            table,
            kind="receipt",
            order_id=make.order(),
            currency="ILS",
            amount_minor=100,
            method="cash",
            occurred_at=STAMP,
        )
    elif table == "equipment_movements":
        item = make.insert("equipment_items", name="Table", category="table")
        row_id = make.insert(table, equipment_item_id=item, movement_type="purchase", quantity=10)
    else:
        item = make.insert("ingredients", name="Flour", base_unit="g")
        batch = make.insert("ingredient_batches", ingredient_id=item, received_on="2026-11-01")
        row_id = make.insert(table, batch_id=batch, movement_type="receipt", quantity=10)
    # The table name is parametrized over a fixed test-only list, never user input.
    original = tuple(conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone())  # noqa: S608
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(
            f"INSERT OR REPLACE INTO {table} SELECT * FROM {table} WHERE id = ?",
            (row_id,),  # noqa: S608
        )  # noqa: S608
    assert (
        tuple(conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()) == original  # noqa: S608
    )  # noqa: S608


def test_replace_by_receipt_document_is_rejected(conn, make):
    order = make.order()
    make.insert(
        "payments",
        kind="receipt",
        order_id=order,
        currency="ILS",
        amount_minor=100,
        method="cash",
        document_number="R1",
        occurred_at=STAMP,
    )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(
            """INSERT OR REPLACE INTO payments
               (kind, order_id, currency, amount_minor, method, document_number, occurred_at)
               VALUES ('receipt', ?, 'ILS', 200, 'cash', 'R1', ?)""",
            (order, STAMP),
        )
    assert conn.execute("SELECT sum(amount_minor) FROM payments").fetchone()[0] == 100


def test_recorded_stock_cannot_change_unit_or_batch_identity(conn, make):
    flour = make.insert("ingredients", name="Flour", base_unit="g")
    sugar = make.insert("ingredients", name="Sugar", base_unit="g")
    batch = make.insert("ingredient_batches", ingredient_id=flour, received_on="2026-11-01")
    make.insert("ingredient_movements", batch_id=batch, movement_type="receipt", quantity=10)
    with pytest.raises(sqlite3.IntegrityError, match="unit of recorded stock"):
        conn.execute("UPDATE ingredients SET base_unit = 'ml' WHERE id = ?", (flour,))
    with pytest.raises(sqlite3.IntegrityError, match="recorded batch"):
        conn.execute("UPDATE ingredient_batches SET ingredient_id = ? WHERE id = ?", (sugar, batch))
    with pytest.raises(sqlite3.IntegrityError, match="recorded batch"):
        conn.execute(
            "UPDATE ingredient_batches SET expires_on = '2027-01-01' WHERE id = ?", (batch,)
        )


def test_delivery_snapshot_survives_address_book_edits(conn, make):
    order, address = make.delivery_order()
    delivery = make.insert("deliveries", order_id=order, address_id=address, **WINDOW)
    snapshot = conn.execute(
        "SELECT address_snapshot FROM deliveries WHERE id = ?", (delivery,)
    ).fetchone()[0]
    assert json.loads(snapshot)["city"] == "תל אביב"
    conn.execute("UPDATE addresses SET city = 'Jerusalem' WHERE id = ?", (address,))
    assert (
        conn.execute(
            "SELECT address_snapshot FROM deliveries WHERE id = ?", (delivery,)
        ).fetchone()[0]
        == snapshot
    )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute("UPDATE deliveries SET address_snapshot = '{}' WHERE id = ?", (delivery,))
    with pytest.raises(sqlite3.IntegrityError, match="new delivery"):
        conn.execute(
            "UPDATE deliveries SET address_id = ? WHERE id = ?", (make.address(None), delivery)
        )


def test_updates_cannot_bypass_food_delivery_requirement(conn, make):
    order, address = make.delivery_order()
    delivery = make.insert("deliveries", order_id=order, address_id=address, **WINDOW)
    with pytest.raises(sqlite3.IntegrityError, match="requires a delivery order"):
        conn.execute("UPDATE deliveries SET order_id = ? WHERE id = ?", (make.order(), delivery))
    with pytest.raises(sqlite3.IntegrityError, match="requires a delivery order"):
        conn.execute(
            "UPDATE orders SET fulfillment_type = 'pickup', delivery_address_id = NULL "
            "WHERE id = ?",
            (order,),
        )
