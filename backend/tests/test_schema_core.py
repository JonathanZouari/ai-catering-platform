"""Customers, addresses, events, orders, employees: constraints the database itself enforces."""

import sqlite3

import pytest

IntegrityError = sqlite3.IntegrityError


def test_customer_needs_a_contact(make):
    with pytest.raises(IntegrityError, match="CHECK"):
        make.customer(phone=None, email=None)


def test_customer_email_unique_case_insensitive(make):
    make.customer(email="Dana@Example.com")
    with pytest.raises(IntegrityError, match="UNIQUE"):
        make.customer(email="dana@example.com")


def test_strict_tables_reject_wrong_types(make):
    customer_id = make.customer()
    with pytest.raises(sqlite3.Error, match="cannot store TEXT value in INTEGER column"):
        make.event(customer_id, adults="twenty")


@pytest.mark.parametrize("bad_date", ["2026-02-30", "20/12/2026", "2026-12-20 10:00"])
def test_dates_must_be_real_iso_dates(make, bad_date):
    customer_id = make.customer()
    with pytest.raises(IntegrityError, match="CHECK"):
        make.event(customer_id, event_date=bad_date)


@pytest.mark.parametrize(
    "bad_ts", ["2026-12-20 16:00:00", "2026-12-20T16:00:00+02:00", "2026-12-20T25:00:00Z"]
)
def test_timestamps_must_be_utc_iso(make, bad_ts):
    with pytest.raises(IntegrityError, match="CHECK"):
        make.order(requested_at=bad_ts)


def test_event_needs_guests(make):
    customer_id = make.customer()
    with pytest.raises(IntegrityError, match="CHECK"):
        make.event(customer_id, adults=0, children=0)


def test_order_event_must_belong_to_same_customer(make):
    alice, bob = make.customer(phone="1"), make.customer(phone="2")
    bobs_event = make.event(bob)
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        make.order(alice, event_id=bobs_event)


def test_order_delivery_address_must_belong_to_customer(make):
    alice, bob = make.customer(phone="1"), make.customer(phone="2")
    bobs_address = make.address(bob)
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        make.order(alice, fulfillment_type="delivery", delivery_address_id=bobs_address)


def test_one_order_per_event(make):
    customer_id = make.customer()
    event_id = make.event(customer_id)
    make.order(customer_id, event_id=event_id)
    with pytest.raises(IntegrityError, match="UNIQUE"):
        make.order(customer_id, event_id=event_id)


def test_pickup_order_cannot_have_address(make):
    customer_id = make.customer()
    with pytest.raises(IntegrityError, match="CHECK"):
        make.order(customer_id, delivery_address_id=make.address(customer_id))


def test_submitted_delivery_order_needs_address_and_frozen_price(make):
    with pytest.raises(IntegrityError, match="CHECK"):
        make.priced_order(fulfillment_type="delivery")  # no address
    with pytest.raises(IntegrityError, match="CHECK"):
        make.order(status="pending_approval")  # no prices


def test_total_must_equal_subtotal_plus_fee(make):
    with pytest.raises(IntegrityError, match="CHECK"):
        make.priced_order(subtotal_minor=10_000, delivery_fee_minor=0, total_minor=10_001)


def test_money_columns_reject_fractions_and_negatives(make):
    with pytest.raises(sqlite3.Error, match="cannot store REAL value"):
        make.priced_order(total_minor=1500.5, subtotal_minor=1500.5)
    with pytest.raises(IntegrityError, match="CHECK"):
        make.priced_order(total_minor=-1, subtotal_minor=-1)


def test_order_status_transitions(conn, make):
    order_id = make.priced_order()
    with pytest.raises(IntegrityError, match="invalid order status transition"):
        conn.execute("UPDATE orders SET status = 'draft' WHERE id = ?", (order_id,))
    conn.execute(
        "UPDATE orders SET status = 'approved', decided_at = '2026-11-02T09:00:00Z' WHERE id = ?",
        (order_id,),
    )
    with pytest.raises(IntegrityError, match="invalid order status transition"):
        conn.execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))


def test_decision_timestamp_required_for_decided_orders(conn, make):
    order_id = make.priced_order()
    with pytest.raises(IntegrityError, match="CHECK"):
        conn.execute("UPDATE orders SET status = 'approved' WHERE id = ?", (order_id,))


def test_customer_with_orders_cannot_be_deleted(conn, make):
    customer_id = make.customer()
    make.order(customer_id)
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))


def test_updated_at_is_maintained(conn, make):
    customer_id = make.customer()
    conn.execute(
        "UPDATE customers SET updated_at = '2000-01-01T00:00:00Z' WHERE id = ?", (customer_id,)
    )
    conn.execute("UPDATE customers SET full_name = 'New Name' WHERE id = ?", (customer_id,))
    updated = conn.execute("SELECT updated_at FROM customers WHERE id = ?", (customer_id,))
    assert updated.fetchone()[0] > "2000-01-01T00:00:00Z"


def test_employee_role_and_flags(make):
    make.employee(role="chef", hired_on="2025-01-15")
    with pytest.raises(IntegrityError, match="CHECK"):
        make.employee(role="astronaut")
    with pytest.raises(IntegrityError, match="CHECK"):
        make.employee(is_active=2)
