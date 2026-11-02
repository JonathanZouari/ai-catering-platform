import datetime
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import init_db
from app.main import app

PHONE = "050-123 4567"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test.db"))
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def payload(**over):
    future = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
    body = {
        "event": {
            "type": "יום הולדת",
            "date": future,
            "slot": "12:00-14:00",
            "fulfillment": "pickup",
            "adults": 10,
            "children": 2,
            "vegetarian": 1,
            "vegan": 0,
            "restricted": 0,
        },
        "items": {"d1": 2, "d5": 0.5},
        "contact": {"name": "נועה", "phone": PHONE},
    }
    body.update(over)
    return body


def rows(client, sql):
    conn = sqlite3.connect(get_settings().sqlite_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def assert_error(response, code, status=422):
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_catalog(client):
    dishes = client.get("/api/catalog/dishes").json()
    assert len(dishes) == 17
    by_id = {d["id"]: d for d in dishes}
    assert by_id["d8"]["allergens"] is None
    assert by_id["d2"]["allergens"] == []
    assert by_id["d1"]["price"] == 85
    assert len(client.get("/api/catalog/categories").json()) == 6
    assert client.get("/api/catalog/zones").json()[0] == {"city": "תל אביב-יפו", "fee": 60}


def test_init_db_rerun_keeps_edits(client):
    conn = sqlite3.connect(get_settings().sqlite_path)
    conn.execute("UPDATE dishes SET price_agorot = 1 WHERE id = 'd1'")
    conn.commit()
    conn.close()
    init_db()
    assert rows(client, "SELECT price_agorot FROM dishes WHERE id = 'd1'") == [(1,)]
    assert rows(client, "SELECT count(*) FROM dishes") == [(17,)]


def test_order_round_trip(client):
    body = payload()
    body["event"].update(fulfillment="delivery", city="הרצליה", address="הרצל 1")
    response = client.post("/api/orders", json=body)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending_approval"
    assert data["subtotal"] == 2 * 85 + 0.5 * 74
    assert data["deliveryFee"] == 90
    assert data["total"] == 170 + 37 + 90
    assert {line["dishId"] for line in data["lines"]} == {"d1", "d5"}
    assert rows(client, "SELECT customer_phone, total_agorot FROM orders") == [
        ("0501234567", 29700)
    ]
    assert rows(client, "SELECT count(*) FROM order_items") == [(2,)]


def test_client_price_rejected(client):
    body = payload(price=1)
    assert_error(client.post("/api/orders", json=body), "validation_error")


def test_unknown_dish_writes_nothing(client):
    response = client.post("/api/orders", json=payload(items={"d1": 1, "nope": 1}))
    assert_error(response, "unknown_dish")
    assert rows(client, "SELECT count(*) FROM orders") == [(0,)]


def test_past_date(client):
    body = payload()
    body["event"]["date"] = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    assert_error(client.post("/api/orders", json=body), "past_date")


@pytest.mark.parametrize("qty", ["NaN", "Infinity", "-1", "0"])
def test_bad_quantity(client, qty):
    # Raw text: Python's json.dumps would refuse to build NaN/Infinity the way a client can.
    text = json.dumps(payload(items={})).replace('"items": {}', f'"items": {{"d1": {qty}}}')
    response = client.post(
        "/api/orders", content=text, headers={"Content-Type": "application/json"}
    )
    assert_error(response, "validation_error")


def test_bad_phone_and_no_echo(client):
    body = payload()
    body["contact"]["phone"] = "12345"
    response = client.post("/api/orders", json=body)
    assert_error(response, "validation_error")
    assert "12345" not in response.text


def test_delivery_without_address(client):
    body = payload()
    body["event"].update(fulfillment="delivery", city="הרצליה", address="  ")
    assert_error(client.post("/api/orders", json=body), "validation_error")


def test_unknown_zone(client):
    body = payload()
    body["event"].update(fulfillment="delivery", city="אילת", address="הים 1")
    assert_error(client.post("/api/orders", json=body), "unknown_zone")


def test_sql_injection_name_stored_verbatim(client):
    evil = "x'); DROP TABLE orders;--"
    body = payload()
    body["contact"]["name"] = evil
    assert client.post("/api/orders", json=body).status_code == 201
    assert rows(client, "SELECT customer_name FROM orders") == [(evil,)]
    assert rows(client, "SELECT count(*) FROM dishes") == [(17,)]
