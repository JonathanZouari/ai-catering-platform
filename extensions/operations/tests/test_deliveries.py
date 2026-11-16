import sqlite3

import pytest

IntegrityError = sqlite3.IntegrityError
WINDOW = {"window_start": "2026-12-20T14:00:00Z", "window_end": "2026-12-20T15:00:00Z"}


def test_delivery_lifecycle(conn, make):
    order_id, address_id = make.delivery_order()
    driver = make.employee()
    delivery_id = make.insert("deliveries", order_id=order_id, address_id=address_id, **WINDOW)
    conn.execute(
        """UPDATE deliveries SET status = 'out_for_delivery', driver_employee_id = ?,
           dispatched_at = '2026-12-20T13:40:00Z' WHERE id = ?""",
        (driver, delivery_id),
    )
    conn.execute(
        """UPDATE deliveries SET status = 'delivered', completed_at = '2026-12-20T14:10:00Z'
           WHERE id = ?""",
        (delivery_id,),
    )
    row = conn.execute("SELECT status FROM deliveries WHERE id = ?", (delivery_id,)).fetchone()
    assert row[0] == "delivered"


def test_food_drop_off_requires_delivery_order(make):
    customer_id = make.customer()
    pickup_order = make.order(customer_id)
    with pytest.raises(IntegrityError, match="requires a delivery order"):
        make.insert(
            "deliveries", order_id=pickup_order, address_id=make.address(customer_id), **WINDOW
        )


def test_equipment_collection_allowed_for_pickup_order(make):
    customer_id = make.customer()
    pickup_order = make.order(customer_id)
    make.insert(
        "deliveries",
        order_id=pickup_order,
        address_id=make.address(customer_id),
        purpose="equipment_collection",
        **WINDOW,
    )


def test_window_must_be_positive(make):
    order_id, address_id = make.delivery_order()
    with pytest.raises(IntegrityError, match="CHECK"):
        make.insert(
            "deliveries",
            order_id=order_id,
            address_id=address_id,
            window_start="2026-12-20T15:00:00Z",
            window_end="2026-12-20T14:00:00Z",
        )


def test_dispatch_requires_driver(make):
    order_id, address_id = make.delivery_order()
    with pytest.raises(IntegrityError, match="CHECK"):
        make.insert(
            "deliveries",
            order_id=order_id,
            address_id=address_id,
            status="out_for_delivery",
            dispatched_at="2026-12-20T13:40:00Z",
            **WINDOW,
        )


def test_delivered_requires_completion_time(make):
    order_id, address_id = make.delivery_order()
    with pytest.raises(IntegrityError, match="CHECK"):
        make.insert(
            "deliveries",
            order_id=order_id,
            address_id=address_id,
            driver_employee_id=make.employee(),
            status="delivered",
            dispatched_at="2026-12-20T13:40:00Z",
            **WINDOW,
        )


def test_unknown_driver_rejected(make):
    order_id, address_id = make.delivery_order()
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        make.insert(
            "deliveries", order_id=order_id, address_id=address_id, driver_employee_id=999, **WINDOW
        )
