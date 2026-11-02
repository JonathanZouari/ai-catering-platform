from datetime import UTC, date, datetime
from decimal import Decimal

from app.models.catalog import Dish, DishCategory
from app.models.orders import Customer, Event, Order, OrderItem
from tests.conftest import AUTH


def add_order(make_session, status="pending_approval", name="דנה", event_date=date(2026, 12, 3)):
    """Insert a submitted order with a frozen price snapshot; returns (order id, dish id)."""
    with make_session() as db:
        dish = Dish(
            category=DishCategory(name=f"cat-{name}-{status}"),
            name="חומוס",
            pricing_unit="per_tray",
            unit_price=Decimal("120"),
        )
        customer = Customer(full_name=name, phone="050-0000000")
        db.add_all([dish, customer])
        db.flush()
        event = Event(
            customer_id=customer.id,
            event_type="בר מצווה",
            event_date=event_date,
            adults=40,
            children=10,
            dietary_notes="בלי אגוזים",
        )
        db.add(event)
        db.flush()
        order = Order(
            customer_id=customer.id,
            event_id=event.id,
            status=status,
            fulfillment_type="pickup",
            requested_at=datetime(2026, 12, 3, 11, tzinfo=UTC),
            subtotal=Decimal("240"),
            total=Decimal("240"),
            submitted_at=None if status == "draft" else datetime.now(UTC),
            items=[
                OrderItem(
                    dish_id=dish.id,
                    quantity=Decimal("2"),
                    snapshot_name="חומוס",
                    snapshot_pricing_unit="per_tray",
                    snapshot_unit_price=Decimal("120"),
                    snapshot_line_total=Decimal("240"),
                )
            ],
        )
        db.add(order)
        db.commit()
        return str(order.id), str(dish.id)


def test_orders_require_token(client, make_session):
    order_id, _ = add_order(make_session)
    assert client.get("/api/admin/orders").status_code == 401
    assert client.post(f"/api/admin/orders/{order_id}/approve").status_code == 401


def test_list_hides_drafts_and_filters(client, make_session):
    pending, _ = add_order(make_session, name="א", event_date=date(2026, 12, 9))
    early, _ = add_order(make_session, name="ב", event_date=date(2026, 12, 1))
    approved, _ = add_order(make_session, "approved", name="ג")
    draft, _ = add_order(make_session, "draft", name="ד")

    everything = client.get("/api/admin/orders", headers=AUTH).json()
    assert [o["id"] for o in everything] == [early, approved, pending]  # by event date, no draft
    assert everything[0]["guests"] == 50 and everything[0]["customer_name"] == "ב"
    only = client.get("/api/admin/orders?status=approved", headers=AUTH).json()
    assert [o["id"] for o in only] == [approved]
    assert client.get("/api/admin/orders?status=draft", headers=AUTH).status_code == 422
    assert client.get(f"/api/admin/orders/{draft}", headers=AUTH).status_code == 404


def test_detail_uses_snapshot(client, make_session):
    order_id, _ = add_order(make_session)
    detail = client.get(f"/api/admin/orders/{order_id}", headers=AUTH).json()
    assert detail["customer"]["full_name"] == "דנה"
    assert detail["event"]["adults"] == 40 and detail["event"]["dietary_notes"] == "בלי אגוזים"
    assert detail["items"] == [
        {
            "dish_id": detail["items"][0]["dish_id"],
            "name": "חומוס",
            "pricing_unit": "per_tray",
            "unit_price": "120.00",
            "quantity": "2.00",
            "line_total": "240.00",
        }
    ]


def test_approve_once(client, make_session):
    order_id, _ = add_order(make_session)
    res = client.post(f"/api/admin/orders/{order_id}/approve", headers=AUTH)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "approved" and body["version"] == 2 and body["decided_at"]
    again = client.post(f"/api/admin/orders/{order_id}/reject", json={"note": "x"}, headers=AUTH)
    assert again.status_code == 409 and again.json()["error"]["code"] == "invalid_transition"


def test_reject_requires_note(client, make_session):
    order_id, _ = add_order(make_session)
    url = f"/api/admin/orders/{order_id}/reject"
    assert client.post(url, json={"note": "   "}, headers=AUTH).status_code == 422
    assert client.post(url, json={}, headers=AUTH).status_code == 422
    res = client.post(url, json={"note": " התאריך תפוס "}, headers=AUTH)
    assert res.json()["status"] == "rejected" and res.json()["decision_note"] == "התאריך תפוס"


def test_dish_in_orders_cannot_be_deleted(client, make_session):
    _, dish_id = add_order(make_session)
    res = client.delete(f"/api/admin/dishes/{dish_id}", headers=AUTH)
    assert res.status_code == 409 and res.json()["error"]["code"] == "dish_in_orders"
