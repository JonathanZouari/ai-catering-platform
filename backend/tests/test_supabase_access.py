"""Live access-control checks against the dev Supabase project. Skipped without credentials.

Run from backend/: uv run --env-file ../.env pytest tests/test_supabase_access.py
"""

import datetime as dt
import os
import uuid

import httpx
import pytest

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
PUBLISHABLE = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
SERVICE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
CUSTOMER_PASSWORD = os.environ.get("DEMO_CUSTOMER_PASSWORD", "")
OWNER_PASSWORD = os.environ.get("DEMO_OWNER_PASSWORD", "")

pytestmark = pytest.mark.skipif(
    not (URL and PUBLISHABLE and SERVICE and CUSTOMER_PASSWORD and OWNER_PASSWORD),
    reason="needs Supabase credentials in the environment",
)


def login(email: str, password: str) -> dict:
    response = httpx.post(
        f"{URL}/auth/v1/token?grant_type=password",
        headers={"apikey": PUBLISHABLE},
        json={"email": email, "password": password},
    )
    response.raise_for_status()
    return response.json()


def client_for(token: str | None) -> httpx.Client:
    headers = {"apikey": PUBLISHABLE}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=URL, headers=headers)


@pytest.fixture(scope="module")
def customer():
    session = login("demo@example.com", CUSTOMER_PASSWORD)
    with client_for(session["access_token"]) as client:
        yield client


@pytest.fixture(scope="module")
def owner():
    session = login("owner@example.com", OWNER_PASSWORD)
    with client_for(session["access_token"]) as client:
        yield client


@pytest.fixture(scope="module")
def service():
    with httpx.Client(
        base_url=URL, headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"}
    ) as client:
        yield client


def rest_count(client: httpx.Client, table: str) -> int:
    response = client.get(f"/rest/v1/{table}", params={"select": "id"})
    response.raise_for_status()
    return len(response.json())


def next_open_date(service: httpx.Client) -> str:
    blocked = {
        row["date"]
        for row in service.get("/rest/v1/blocked_dates", params={"select": "date"}).json()
    }
    day = dt.date.today() + dt.timedelta(days=3)
    while day.isoformat() in blocked:
        day += dt.timedelta(days=1)
    return day.isoformat()


def order_payload(service: httpx.Client, dish_id: str, **extra) -> dict:
    return {
        "event": {
            "type": "בדיקה",
            "date": next_open_date(service),
            "slot": "10:00-12:00",
            "fulfillment": "pickup",
            "adults": 5,
        },
        "items": [{"dish_id": dish_id, "quantity": 2, **extra}],
        "contact": {"name": "לקוח דמו", "phone": "0500000000"},
    }


def first_dish(service: httpx.Client) -> dict:
    return service.get(
        "/rest/v1/dishes", params={"select": "id,unit_price", "name": "eq.חומוס ביתי"}
    ).json()[0]


def remove_order(service: httpx.Client, order_id: str) -> None:
    event = service.get(
        "/rest/v1/orders", params={"select": "event_id", "id": f"eq.{order_id}"}
    ).json()[0]
    service.delete("/rest/v1/orders", params={"id": f"eq.{order_id}"}).raise_for_status()
    service.delete("/rest/v1/events", params={"id": f"eq.{event['event_id']}"}).raise_for_status()


@pytest.mark.parametrize("table", ["dishes", "orders", "customers", "ai_messages"])
def test_anonymous_visitor_reads_nothing(table):
    with client_for(None) as anon:
        assert anon.get(f"/rest/v1/{table}").status_code == 401


def test_customer_sees_only_their_own_orders(customer, owner):
    assert rest_count(customer, "orders") == rest_count(customer, "events")
    mine = customer.get("/rest/v1/orders", params={"select": "customer_id"}).json()
    assert mine and len({row["customer_id"] for row in mine}) == 1
    assert rest_count(customer, "customers") == 1
    assert rest_count(owner, "orders") > len(mine)
    assert rest_count(owner, "customers") > 1


def test_customer_cannot_write_orders_or_prices(customer, service):
    order = customer.get("/rest/v1/orders", params={"select": "id,total,status"}).json()[0]
    changed = customer.patch(
        "/rest/v1/orders",
        params={"id": f"eq.{order['id']}"},
        json={"total": 1, "status": "approved"},
    )
    assert changed.status_code in (401, 403)
    assert customer.post("/rest/v1/orders", json={}).status_code in (401, 403)

    dish = first_dish(service)
    customer.patch("/rest/v1/dishes", params={"id": f"eq.{dish['id']}"}, json={"unit_price": 1})
    assert first_dish(service)["unit_price"] == dish["unit_price"]

    after = service.get(
        "/rest/v1/orders", params={"select": "total,status", "id": f"eq.{order['id']}"}
    ).json()[0]
    assert after == {"total": order["total"], "status": order["status"]}


def test_customer_cannot_become_admin_through_metadata(customer):
    response = customer.put("/auth/v1/user", json={"data": {"role": "admin"}})
    response.raise_for_status()
    assert response.json()["app_metadata"].get("role") != "admin"
    session = login("demo@example.com", CUSTOMER_PASSWORD)
    with client_for(session["access_token"]) as refreshed:
        assert rest_count(refreshed, "customers") == 1
    customer.put("/auth/v1/user", json={"data": {"role": None}})


def test_submit_uses_server_price_and_only_owner_decides(customer, owner, service):
    dish = first_dish(service)
    forged = order_payload(service, dish["id"], unit_price=1, total=1)
    response = customer.post("/rest/v1/rpc/submit_order", json={"payload": forged})
    assert response.status_code == 200, response.text
    result = response.json()
    try:
        assert float(result["total"]) == float(dish["unit_price"]) * 2

        call = {"order_id": result["id"], "decision": "approved"}
        assert customer.post("/rest/v1/rpc/decide_order", json=call).status_code == 403
        assert owner.post("/rest/v1/rpc/decide_order", json=call).status_code in (200, 204)
        row = customer.get(
            "/rest/v1/orders", params={"select": "status", "id": f"eq.{result['id']}"}
        ).json()[0]
        assert row["status"] == "approved"
        # A decided order cannot be decided again.
        again = {"order_id": result["id"], "decision": "rejected"}
        assert owner.post("/rest/v1/rpc/decide_order", json=again).status_code >= 400
    finally:
        remove_order(service, result["id"])


def test_only_admin_writes_dish_images(customer, owner):
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"
    )
    path = f"test/{uuid.uuid4()}.png"
    headers = {"Content-Type": "image/png"}
    denied = customer.post(f"/storage/v1/object/dish-images/{path}", content=png, headers=headers)
    assert denied.status_code >= 400

    uploaded = owner.post(f"/storage/v1/object/dish-images/{path}", content=png, headers=headers)
    assert uploaded.status_code == 200, uploaded.text
    try:
        public = httpx.get(f"{URL}/storage/v1/object/public/dish-images/{path}")
        assert public.status_code == 200
        forbidden = customer.delete(f"/storage/v1/object/dish-images/{path}")
        assert httpx.get(f"{URL}/storage/v1/object/public/dish-images/{path}").status_code == 200, (
            forbidden.text
        )
    finally:
        owner.delete(f"/storage/v1/object/dish-images/{path}").raise_for_status()
