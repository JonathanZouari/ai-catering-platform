import datetime
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

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
    conn.execute("UPDATE dishes SET price = 1 WHERE id = 'd1'")
    conn.commit()
    conn.close()
    init_db()
    assert rows(client, "SELECT price FROM dishes WHERE id = 'd1'") == [(1,)]
    assert rows(client, "SELECT count(*) FROM dishes") == [(17,)]


def test_order_round_trip(client):
    body = payload()
    body["event"].update(fulfillment="delivery", city="הרצליה", address="הרצל 1")
    response = client.post("/api/orders", json=body)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending_approval"
    assert data["subtotal"] == 2 * 85 + 37
    assert data["deliveryFee"] == 90
    assert data["total"] == 170 + 37 + 90
    assert {line["dishId"] for line in data["lines"]} == {"d1", "d5"}
    assert rows(client, "SELECT customer_phone, total FROM orders") == [("0501234567", 297)]
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


def test_half_up_rounding(client):
    response = client.post("/api/orders", json=payload(items={"d10": 0.5}))
    assert response.status_code == 201
    data = response.json()
    assert data["lines"][0]["lineTotal"] == 73  # 72.5 rounds up, not banker's 72
    assert data["total"] == 73
    assert isinstance(data["total"], int)


@pytest.mark.parametrize("items", [{"d1": 0.5}, {"d5": 0.3}, {"d13": 1}, {"d1": 0.001}])
def test_invalid_quantity_writes_nothing(client, items):
    assert_error(client.post("/api/orders", json=payload(items=items)), "invalid_quantity")
    assert rows(client, "SELECT count(*) FROM orders") == [(0,)]
    assert rows(client, "SELECT count(*) FROM order_items") == [(0,)]


@pytest.mark.parametrize("items", [{"d13": 8}, {"d5": 1.5}])
def test_valid_quantity_accepted(client, items):
    assert client.post("/api/orders", json=payload(items=items)).status_code == 201


ORDER = (
    "INSERT INTO orders VALUES ('o', 'draft', '{name}', '{phone}', '{{}}',"
    " {sub}, {fee}, {total}, 't')"
)


@pytest.mark.parametrize(
    "bad",
    [
        {"phone": ""},
        {"phone": "05012x4567"},
        {"phone": "12345"},
        {"total": -1, "sub": -1},
        {"total": 5},
        {"name": ""},
    ],
)
def test_db_rejects_bad_order(client, bad):
    args = {"name": "x", "phone": "0501234567", "sub": 10, "fee": 0, "total": 10} | bad
    conn = sqlite3.connect(get_settings().sqlite_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(ORDER.format(**args))
    finally:
        conn.close()


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE dishes SET price = 72.5 WHERE id = 'd1'",
        "UPDATE dishes SET name = '' WHERE id = 'd1'",
    ],
)
def test_db_rejects_bad_dish(client, sql):
    conn = sqlite3.connect(get_settings().sqlite_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql)
    finally:
        conn.close()


@pytest.mark.parametrize(("env", "status"), [("production", 404), ("development", 200)])
def test_openapi_only_in_development(env, status):
    # The app is built at import time, so check it in a fresh interpreter.
    code = (
        "from fastapi.testclient import TestClient; from app.main import app;"
        "print(TestClient(app).get('/openapi.json').status_code)"
    )
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "APP_ENV": env},
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == str(status)
