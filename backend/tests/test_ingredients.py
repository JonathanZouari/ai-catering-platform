import sqlite3
from datetime import UTC, date, datetime, timedelta

import pytest

from app.repositories.inventory import InsufficientStock, consume_ingredient, expiring_batches

IntegrityError = sqlite3.IntegrityError


@pytest.fixture
def flour(make):
    return make.insert("ingredients", name="Flour", base_unit="g", reorder_level=5000)


def batch(make, ingredient, received_on, expires_on, quantity, lot=None):
    batch_id = make.insert(
        "ingredient_batches",
        ingredient_id=ingredient,
        lot_code=lot,
        received_on=received_on,
        expires_on=expires_on,
        total_cost_minor=quantity // 10,
    )
    make.insert(
        "ingredient_movements",
        batch_id=batch_id,
        movement_type="receipt",
        quantity=quantity,
        occurred_at=f"{received_on}T08:00:00Z",
    )
    return batch_id


def on_hand(conn, batch_id):
    return conn.execute(
        "SELECT on_hand FROM ingredient_batch_stock WHERE batch_id = ?", (batch_id,)
    ).fetchone()[0]


def test_fefo_consumption_spans_batches(conn, make, flour):
    late = batch(make, flour, "2026-10-01", "2027-03-01", 4000, lot="L-late")
    early = batch(make, flour, "2026-10-15", "2026-12-01", 3000, lot="L-early")
    keeps = batch(make, flour, "2026-10-01", None, 1000, lot="L-dry")
    order_id = make.order()

    draws = consume_ingredient(
        conn,
        ingredient_id=flour,
        quantity=5000,
        order_id=order_id,
        occurred_at=datetime(2026, 11, 2, 10, tzinfo=UTC),
    )

    assert [(d.batch_id, d.quantity) for d in draws] == [(early, 3000), (late, 2000)]
    assert (on_hand(conn, early), on_hand(conn, late), on_hand(conn, keeps)) == (0, 2000, 1000)


def test_expired_batches_are_skipped_and_refused(conn, make, flour):
    expired = batch(make, flour, "2026-09-01", "2026-10-01", 2000)
    fresh = batch(make, flour, "2026-10-20", "2027-01-01", 500)
    when = datetime(2026, 11, 2, 10, tzinfo=UTC)

    with pytest.raises(InsufficientStock, match="usable on hand 500"):
        consume_ingredient(conn, ingredient_id=flour, quantity=600, occurred_at=when)
    assert on_hand(conn, fresh) == 500  # all-or-nothing

    with pytest.raises(IntegrityError, match="cannot consume an expired batch"):
        make.insert(
            "ingredient_movements",
            batch_id=expired,
            movement_type="consumption",
            quantity=1,
            occurred_at="2026-11-02T10:00:00Z",
        )
    # Disposal of the expired stock is allowed and recorded.
    make.insert(
        "ingredient_movements",
        batch_id=expired,
        movement_type="expired_disposal",
        quantity=2000,
        occurred_at="2026-11-02T10:00:00Z",
    )
    assert on_hand(conn, expired) == 0


def test_batch_cannot_go_negative(make, flour):
    batch_id = batch(make, flour, "2026-10-01", "2027-01-01", 100)
    with pytest.raises(IntegrityError, match="not enough of this batch"):
        make.insert(
            "ingredient_movements",
            batch_id=batch_id,
            movement_type="waste",
            quantity=101,
            notes="spilled",
            occurred_at="2026-11-02T10:00:00Z",
        )


def test_movement_cannot_predate_receipt(make, flour):
    batch_id = make.insert("ingredient_batches", ingredient_id=flour, received_on="2026-10-10")
    with pytest.raises(IntegrityError, match="before the batch was received"):
        make.insert(
            "ingredient_movements",
            batch_id=batch_id,
            movement_type="receipt",
            quantity=10,
            occurred_at="2026-10-09T23:00:00Z",
        )


def test_expiry_cannot_precede_receipt(make, flour):
    with pytest.raises(IntegrityError, match="CHECK"):
        make.insert(
            "ingredient_batches",
            ingredient_id=flour,
            received_on="2026-10-10",
            expires_on="2026-10-09",
        )


def test_lot_code_unique_per_ingredient(make, flour):
    sugar = make.insert("ingredients", name="Sugar", base_unit="g")
    make.insert("ingredient_batches", ingredient_id=flour, lot_code="A1", received_on="2026-10-01")
    make.insert("ingredient_batches", ingredient_id=sugar, lot_code="A1", received_on="2026-10-01")
    with pytest.raises(IntegrityError, match="UNIQUE"):
        make.insert(
            "ingredient_batches", ingredient_id=flour, lot_code="A1", received_on="2026-10-02"
        )


def test_quantities_are_integer_base_units(make, flour):
    batch_id = make.insert("ingredient_batches", ingredient_id=flour, received_on="2026-10-01")
    with pytest.raises(sqlite3.Error, match="cannot store REAL value"):
        make.insert(
            "ingredient_movements",
            batch_id=batch_id,
            movement_type="receipt",
            quantity=2.5,
            occurred_at="2026-10-01T08:00:00Z",
        )
    with pytest.raises(IntegrityError, match="CHECK"):
        make.insert("ingredients", name="Oil", base_unit="litre")


def test_stock_views_split_usable_and_expired(conn, make, flour):
    today = date.today()
    batch(
        make,
        flour,
        (today - timedelta(days=30)).isoformat(),
        (today - timedelta(days=1)).isoformat(),
        700,
    )
    soon = batch(
        make,
        flour,
        (today - timedelta(days=5)).isoformat(),
        (today + timedelta(days=3)).isoformat(),
        300,
    )
    batch(
        make,
        flour,
        (today - timedelta(days=5)).isoformat(),
        (today + timedelta(days=60)).isoformat(),
        900,
    )

    row = conn.execute(
        "SELECT usable_on_hand, expired_on_hand, reorder_level FROM ingredient_stock "
        "WHERE ingredient_id = ?",
        (flour,),
    ).fetchone()
    assert tuple(row) == (1200, 700, 5000)

    upcoming = expiring_batches(conn, today + timedelta(days=7))
    assert [r["batch_id"] for r in upcoming][-1] == soon
    assert len(upcoming) == 2  # the expired one and the one expiring soon


def test_ingredient_movements_are_append_only(conn, make, flour):
    batch_id = batch(make, flour, "2026-10-01", None, 10)
    with pytest.raises(IntegrityError, match="append-only"):
        conn.execute("DELETE FROM ingredient_movements WHERE batch_id = ?", (batch_id,))
