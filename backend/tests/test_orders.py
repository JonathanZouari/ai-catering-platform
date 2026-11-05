from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.dishes import get_db
from app.db import connect, seed
from app.main import app


@pytest.fixture
def env(tmp_path):
    path = str(tmp_path / "t.db")
    seed.seed(path)
    app.dependency_overrides[get_db] = lambda: connect(path)
    yield TestClient(app), path
    app.dependency_overrides.clear()


def payload(**event):
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
        "items": [{"dish_id": "dish-1", "quantity": 2}],
    }


def test_availability(env):
    client, _ = env
    data = client.get("/api/availability").json()
    assert data["min_date"] == (date.today() + timedelta(days=2)).isoformat()
    assert len(data["blocked_dates"]) == 2
    assert {z["city"]: z["fee"] for z in data["zones"]}["הרצליה"] == 9000
    assert data["slots"]["pickup"][0] == "10:00-12:00"


def test_create_order_prices_on_server_and_persists(env):
    client, path = env
    r = client.post("/api/orders", json=payload())
    assert r.status_code == 201
    order = r.json()
    assert order["status"] == "pending_approval"
    assert order["snapshot"]["total"] == 24000  # 2 trays x 120.00 NIS, pickup has no fee
    db = connect(path)
    assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 1
    assert db.execute("SELECT full_name FROM customers").fetchone()[0] == "נועה לוי"


def test_delivery_adds_zone_fee(env):
    client, _ = env
    body = payload(fulfillment="delivery", slot="09:00-11:00", city="הרצליה", address="הרצל 1")
    snap = client.post("/api/orders", json=body).json()["snapshot"]
    assert (snap["subtotal"], snap["delivery_fee"], snap["total"]) == (24000, 9000, 33000)


def test_snapshot_is_frozen_after_price_change(env):
    client, path = env
    order_id = client.post("/api/orders", json=payload()).json()["id"]
    db = connect(path)
    db.execute("UPDATE dishes SET unit_price = 99999")
    db.commit()
    assert client.get(f"/api/orders/{order_id}").json()["snapshot"]["total"] == 24000


@pytest.mark.parametrize(
    ("event", "field"),
    [
        ({"date": (date.today() + timedelta(days=1)).isoformat()}, "date"),  # inside lead time
        ({"date": (date.today() + timedelta(days=5)).isoformat()}, "date"),  # blocked by the seed
        ({"slot": "03:00-04:00"}, "slot"),
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
def test_event_validation(env, event, field):
    client, path = env
    r = client.post("/api/orders", json=payload(**event))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert field in r.json()["error"]["details"]
    assert connect(path).execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0


def test_contact_and_items_validation(env):
    client, _ = env
    body = payload()
    body["contact"] = {"name": " ", "phone": "123"}
    body["items"] = []
    details = client.post("/api/orders", json=body).json()["error"]["details"]
    assert {"name", "phone", "items"} <= details.keys()


def test_unknown_dish_rejected(env):
    client, _ = env
    body = payload()
    body["items"] = [{"dish_id": "nope", "quantity": 1}]
    assert "items" in client.post("/api/orders", json=body).json()["error"]["details"]


def test_get_unknown_order_is_404(env):
    client, _ = env
    r = client.get("/api/orders/missing")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
