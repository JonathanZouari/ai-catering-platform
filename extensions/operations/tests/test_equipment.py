import sqlite3

import pytest

from extensions.operations.repositories.inventory import equipment_stock

IntegrityError = sqlite3.IntegrityError


@pytest.fixture
def tables(make):
    return make.insert(
        "equipment_items", name="Round table 150cm", category="table", replacement_cost_minor=45_000
    )


def move(make, item, movement_type, quantity, **extra):
    return make.insert(
        "equipment_movements",
        equipment_item_id=item,
        movement_type=movement_type,
        quantity=quantity,
        **extra,
    )


def stock(conn, item):
    return conn.execute(
        "SELECT on_hand, out_at_events FROM equipment_stock WHERE equipment_item_id = ?", (item,)
    ).fetchone()


def test_dispatch_return_and_loss(conn, make, tables):
    order_id, address_id = make.delivery_order()
    delivery_id = make.insert(
        "deliveries",
        order_id=order_id,
        address_id=address_id,
        window_start="2026-12-20T14:00:00Z",
        window_end="2026-12-20T15:00:00Z",
    )
    move(make, tables, "purchase", 20)
    move(make, tables, "dispatch", 8, order_id=order_id, delivery_id=delivery_id)
    assert tuple(stock(conn, tables)) == (12, 8)
    move(make, tables, "return", 7, order_id=order_id)
    move(make, tables, "lost_at_event", 1, order_id=order_id, notes="leg broken")
    assert tuple(stock(conn, tables)) == (19, 0)
    move(make, tables, "write_off", 2, notes="water damage in storage")
    assert tuple(stock(conn, tables)) == (17, 0)

    rows = equipment_stock(conn)
    assert [(r["name"], r["on_hand"]) for r in rows] == [("Round table 150cm", 17)]


def test_cannot_dispatch_more_than_on_hand(make, tables):
    move(make, tables, "purchase", 5)
    with pytest.raises(IntegrityError, match="not enough equipment on hand"):
        move(make, tables, "dispatch", 6, order_id=make.order())


def test_cannot_return_more_than_dispatched_to_that_order(make, tables):
    order_a, order_b = make.order(), make.order()
    move(make, tables, "purchase", 10)
    move(make, tables, "dispatch", 4, order_id=order_a)
    with pytest.raises(IntegrityError, match="more equipment returned"):
        move(make, tables, "return", 1, order_id=order_b)
    with pytest.raises(IntegrityError, match="more equipment returned"):
        move(make, tables, "return", 5, order_id=order_a)


def test_order_link_rules(make, tables):
    move(make, tables, "purchase", 10)
    with pytest.raises(IntegrityError, match="CHECK"):
        move(make, tables, "dispatch", 1)  # dispatch needs an order
    with pytest.raises(IntegrityError, match="CHECK"):
        move(make, tables, "purchase", 1, order_id=make.order())  # purchase must not have one
    with pytest.raises(IntegrityError, match="CHECK"):
        move(make, tables, "write_off", 1)  # write-off needs a note


def test_delivery_must_belong_to_same_order(make, tables):
    order_a, address_a = make.delivery_order()
    order_b = make.order()
    delivery_a = make.insert(
        "deliveries",
        order_id=order_a,
        address_id=address_a,
        window_start="2026-12-20T14:00:00Z",
        window_end="2026-12-20T15:00:00Z",
    )
    move(make, tables, "purchase", 10)
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        move(make, tables, "dispatch", 1, order_id=order_b, delivery_id=delivery_a)


def test_category_is_tables_or_serving_utensils(make):
    make.insert("equipment_items", name="Chafing dish", category="serving_utensil")
    with pytest.raises(IntegrityError, match="CHECK"):
        make.insert("equipment_items", name="Paper plates", category="disposable")
    with pytest.raises(IntegrityError, match="UNIQUE"):
        make.insert("equipment_items", name="CHAFING DISH", category="serving_utensil")


def test_movements_are_append_only(conn, make, tables):
    movement = move(make, tables, "purchase", 3)
    with pytest.raises(IntegrityError, match="append-only"):
        conn.execute("UPDATE equipment_movements SET quantity = 30 WHERE id = ?", (movement,))
    with pytest.raises(IntegrityError, match="append-only"):
        conn.execute("DELETE FROM equipment_movements WHERE id = ?", (movement,))
