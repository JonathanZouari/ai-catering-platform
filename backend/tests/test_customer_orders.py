import uuid
from datetime import date

import pytest

from app.services import customer_orders
from tests.conftest import AUTH, token

pytestmark = pytest.mark.usefixtures("supabase")

TODAY = date(2027, 3, 1)
EVENT_DAY = date(2027, 3, 11)
WEEKDAY = (EVENT_DAY.weekday() + 1) % 7  # Sun=0 convention


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(customer_orders, "today", lambda: TODAY)


@pytest.fixture
def setup(client):
    """A customer with a profile plus pickup/delivery slots; returns (headers, slots)."""
    headers = token(uuid.uuid4(), email="dana@example.com")
    client.put("/api/me", json={"full_name": "דנה לוי", "phone": "050-1234567"}, headers=headers)
    slot = lambda kind, day, start="10:00", end="12:00", active=True: client.post(  # noqa: E731
        "/api/admin/time-slots",
        json={
            "fulfillment_type": kind,
            "weekday": day,
            "start_time": start,
            "end_time": end,
            "is_active": active,
        },
        headers=AUTH,
    ).json()["id"]
    slots = {
        "pickup": slot("pickup", WEEKDAY),
        "delivery_any_day": slot("delivery", None, "18:00", "20:00"),
        "pickup_other_day": slot("pickup", (WEEKDAY + 1) % 7),
        "inactive": slot("pickup", WEEKDAY, active=False),
    }
    return headers, slots


def draft(slot_id, **over):
    event = {
        "event_type": "בר מצווה",
        "event_date": EVENT_DAY.isoformat(),
        "adults": 40,
        "children": 10,
        "vegetarian_guests": 5,
        "vegan_guests": 2,
    }
    event.update(over.pop("event", {}))
    return {"event": event, "fulfillment_type": "pickup", "slot_id": slot_id, **over}


def test_requires_login_and_profile(client, setup):
    _, slots = setup
    assert client.post("/api/orders", json=draft(slots["pickup"])).status_code == 401
    no_profile = token()  # signed in but never saved a profile
    res = client.post("/api/orders", json=draft(slots["pickup"]), headers=no_profile)
    assert res.status_code == 409 and res.json()["error"]["code"] == "profile_required"


def test_create_draft(client, setup):
    headers, slots = setup
    res = client.post("/api/orders", json=draft(slots["pickup"]), headers=headers)
    assert res.status_code == 201, res.text
    order = res.json()
    assert order["status"] == "draft" and order["version"] == 1
    assert order["event"]["adults"] == 40 and order["event"]["vegan_guests"] == 2
    # 10:00 Israel time (UTC+2 in March) is stored and returned as UTC, with tzinfo
    assert order["requested_at"] == "2027-03-11T08:00:00Z"
    assert order["delivery_address"] is None
    mine = client.get("/api/me/orders", headers=headers).json()
    assert [o["id"] for o in mine] == [order["id"]] and mine[0]["status"] == "draft"


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"event": {"adults": 0, "children": 0}}, "adults"),
        ({"event": {"vegetarian_guests": 51}}, "vegetarian_guests"),  # subset of 50 guests
        ({"event": {"vegan_guests": 51}}, "vegan_guests"),
        ({"event": {"restricted_guests": 51}}, "restricted_guests"),
        ({"event": {"event_date": "2027-02-28"}}, "event_date"),  # before TODAY
        ({"fulfillment_type": "delivery"}, "slot_id"),  # pickup slot used for delivery
    ],
)
def test_validation(client, setup, change, field):
    headers, slots = setup
    res = client.post("/api/orders", json=draft(slots["pickup"], **change), headers=headers)
    assert res.status_code == 422, res.text
    assert res.json()["error"]["details"]["field"] == field


def test_slot_and_date_rules(client, setup):
    headers, slots = setup
    for name in ("pickup_other_day", "inactive"):
        res = client.post("/api/orders", json=draft(slots[name]), headers=headers)
        assert res.json()["error"]["code"] == "slot_unavailable", name
    assert (
        client.post("/api/orders", json=draft(str(uuid.uuid4())), headers=headers).status_code
        == 422
    )

    client.post("/api/admin/blocked-dates", json={"date": EVENT_DAY.isoformat()}, headers=AUTH)
    res = client.post("/api/orders", json=draft(slots["pickup"]), headers=headers)
    assert res.json()["error"]["code"] == "date_unavailable"


def test_delivery_needs_address(client, setup):
    headers, slots = setup
    body = draft(slots["delivery_any_day"], fulfillment_type="delivery")
    res = client.post("/api/orders", json=body, headers=headers)
    assert res.json()["error"]["details"]["field"] == "delivery_address"
    res = client.post(
        "/api/orders", json={**body, "delivery_address": " הרצל 10, רמת גן "}, headers=headers
    )
    assert res.status_code == 201 and res.json()["delivery_address"] == "הרצל 10, רמת גן"


def test_update_with_version(client, setup):
    headers, slots = setup
    order = client.post("/api/orders", json=draft(slots["pickup"]), headers=headers).json()
    url = f"/api/orders/{order['id']}"
    body = draft(slots["pickup"], event={"adults": 60}, version=1)
    res = client.patch(url, json=body, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["version"] == 2 and res.json()["event"]["adults"] == 60
    stale = client.patch(url, json=body, headers=headers)  # still says version 1
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "order_version_conflict"
    # switching to delivery clears nothing it shouldn't and keeps the address
    body = draft(
        slots["delivery_any_day"],
        fulfillment_type="delivery",
        delivery_address="הנשיא 4",
        version=2,
    )
    assert client.patch(url, json=body, headers=headers).json()["delivery_address"] == "הנשיא 4"


def test_other_customer_cannot_see_or_edit(client, setup):
    headers, slots = setup
    order = client.post("/api/orders", json=draft(slots["pickup"]), headers=headers).json()
    stranger = token(uuid.uuid4(), email="eve@example.com")
    client.put("/api/me", json={"full_name": "איב", "phone": "050-9999999"}, headers=stranger)
    url = f"/api/orders/{order['id']}"
    assert client.get(url, headers=stranger).status_code == 404
    patch = client.patch(url, json=draft(slots["pickup"], version=1), headers=stranger)
    assert patch.status_code == 404
    assert client.get(url, headers=headers).status_code == 200


def test_only_drafts_are_editable(client, setup, make_session):
    from app.models.orders import Order

    headers, slots = setup
    order = client.post("/api/orders", json=draft(slots["pickup"]), headers=headers).json()
    with make_session() as db:
        db.get(Order, uuid.UUID(order["id"])).status = "pending_approval"
        db.commit()
    res = client.patch(
        f"/api/orders/{order['id']}", json=draft(slots["pickup"], version=1), headers=headers
    )
    assert res.status_code == 409 and res.json()["error"]["code"] == "invalid_transition"


def test_mass_assignment_rejected(client, setup):
    headers, slots = setup
    for extra in ({"status": "approved"}, {"version": 9}, {"customer_id": str(uuid.uuid4())}):
        res = client.post("/api/orders", json={**draft(slots["pickup"]), **extra}, headers=headers)
        assert res.status_code == 422, extra
