from datetime import date, timedelta

import pytest


def dish_id(db, name="חומוס ביתי"):
    return str(db.execute("SELECT id FROM dishes WHERE name = %s", (name,)).fetchone()["id"])


def count(db, table):
    return db.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]  # noqa: S608


@pytest.fixture(autouse=True)
def blocked_day(db):
    db.execute(
        "INSERT INTO blocked_dates (date, reason) VALUES (%s, 'test') ON CONFLICT DO NOTHING",
        (date.today() + timedelta(days=5),),
    )


def payload(db, **event):
    ev = {
        "type": "יום הולדת",
        "date": (date.today() + timedelta(days=7)).isoformat(),
        "slot": "10:00-12:00",
        "fulfillment": "pickup",
        "adults": 10,
        "children": 2,
    }
    ev.update(event)
    return {
        "event": ev,
        "contact": {"name": "נועה לוי", "phone": "050-1234567"},
        "items": [{"dish_id": dish_id(db), "quantity": 2}],
    }


def test_availability(client):
    data = client.get("/api/availability").json()
    assert data["min_date"] == (date.today() + timedelta(days=2)).isoformat()
    assert (date.today() + timedelta(days=5)).isoformat() in data["blocked_dates"]
    assert {z["city"]: z["fee"] for z in data["zones"]}["הרצליה"] == 9000
    assert data["slots"]["pickup"][0] == "10:00-12:00"


def test_create_order_prices_on_server_and_persists(client, db):
    before = count(db, "orders")
    r = client.post("/api/orders", json=payload(db))
    assert r.status_code == 201
    order = r.json()
    assert order["status"] == "pending_approval"
    assert order["snapshot"]["total"] == 24000  # 2 trays x 120.00 NIS, pickup has no fee
    assert count(db, "orders") == before + 1
    assert db.execute("SELECT 1 FROM customers WHERE full_name = 'נועה לוי'").fetchone()


def test_delivery_adds_zone_fee(client, db):
    body = payload(db, fulfillment="delivery", slot="09:00-11:00", city="הרצליה", address="הרצל 1")
    snap = client.post("/api/orders", json=body).json()["snapshot"]
    assert (snap["subtotal"], snap["delivery_fee"], snap["total"]) == (24000, 9000, 33000)


def test_snapshot_is_frozen_after_price_change(client, db):
    order_id = client.post("/api/orders", json=payload(db)).json()["id"]
    db.execute("UPDATE dishes SET unit_price = 99999")
    assert client.get(f"/api/orders/{order_id}").json()["snapshot"]["total"] == 24000


@pytest.mark.parametrize(
    ("event", "field"),
    [
        ({"date": (date.today() + timedelta(days=1)).isoformat()}, "date"),  # inside lead time
        ({"date": (date.today() + timedelta(days=5)).isoformat()}, "date"),  # blocked day
        ({"slot": "03:00-04:00"}, "slot"),
        ({"slot": "garbage"}, "slot"),
        ({"adults": 0, "children": 0}, "adults"),
        ({"vegan": 50}, "dietary"),
        ({"fulfillment": "delivery", "slot": "09:00-11:00"}, "city"),
        ({"fulfillment": "delivery", "slot": "09:00-11:00", "city": "הרצליה"}, "address"),
        (
            {"fulfillment": "delivery", "slot": "09:00-11:00", "city": "אילת", "address": "x"},
            "city",
        ),
    ],
)
def test_event_validation(client, db, event, field):
    before = count(db, "orders")
    r = client.post("/api/orders", json=payload(db, **event))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert field in r.json()["error"]["details"]
    assert count(db, "orders") == before


def test_contact_and_items_validation(client, db):
    body = payload(db)
    body["contact"] = {"name": " ", "phone": "123"}
    body["items"] = []
    details = client.post("/api/orders", json=body).json()["error"]["details"]
    assert {"name", "phone", "items"} <= details.keys()


def test_unknown_dish_rejected(client, db):
    body = payload(db)
    body["items"] = [{"dish_id": "nope", "quantity": 1}]
    assert "items" in client.post("/api/orders", json=body).json()["error"]["details"]


@pytest.mark.parametrize("order_id", ["missing", "00000000-0000-0000-0000-000000000000"])
def test_get_unknown_order_is_404(client, order_id):
    r = client.get(f"/api/orders/{order_id}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
