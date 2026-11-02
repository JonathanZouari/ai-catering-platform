"""Phase 3 slice 4: submit (price snapshot), withdraw, slot capacity, notifications."""

import uuid

import pytest

from tests.conftest import AUTH, token
from tests.test_customer_orders import (  # noqa: F401  (fixtures are used by name)
    EVENT_DAY,
    draft,
    fixed_today,
    menu,
    setup,
)

pytestmark = pytest.mark.usefixtures("supabase")


@pytest.fixture
def outbox(monkeypatch):
    """Capture emails instead of sending them."""
    from app.core import config, mailer

    sent = []
    monkeypatch.setattr(mailer, "send", sent.append)
    monkeypatch.setattr(config.get_settings(), "owner_email", "owner@example.com")
    return sent


def draft_with_item(client, headers, slot_id, dish_id, quantity="3"):
    order = client.post("/api/orders", json=draft(slot_id), headers=headers).json()
    url = f"/api/orders/{order['id']}"
    body = {"quantity": quantity, "version": 1}
    return url, client.put(f"{url}/items/{dish_id}", json=body, headers=headers).json()["version"]


def test_submit_freezes_prices_and_notifies_owner(client, setup, outbox):
    headers, slots = setup
    tray, kg, _ = menu(client)
    url, version = draft_with_item(client, headers, slots["pickup"], tray)
    body = {"quantity": "2.5", "version": version}
    version = client.put(f"{url}/items/{kg}", json=body, headers=headers).json()["version"]

    res = client.post(f"{url}/submit", json={"version": version}, headers=headers)
    assert res.status_code == 200, res.text
    order = res.json()
    assert order["status"] == "pending_approval" and order["submitted_at"]
    assert order["subtotal"] == "909.98" and order["total"] == "909.98"

    # The owner changes a price afterwards: the submitted order keeps its snapshot.
    client.patch(f"/api/admin/dishes/{tray}", json={"unit_price": "999"}, headers=AUTH)
    assert client.get(f"{url}/pricing", headers=headers).json()["total"] == "909.98"
    detail = client.get(f"/api/admin/orders/{order['id']}", headers=AUTH).json()
    assert {i["name"]: i["line_total"] for i in detail["items"]} == {
        "בריסקט": "549.98",
        "חומוס": "360.00",
    }

    assert [e.to for e in outbox] == ["owner@example.com"]
    assert "דנה לוי" in outbox[0].subject and "909.98" in outbox[0].body

    # submitted orders are locked for edits
    body = {"quantity": "4", "version": order["version"]}
    again = client.put(f"{url}/items/{tray}", json=body, headers=headers)
    assert again.json()["error"]["code"] == "invalid_transition"


def test_submit_rechecks_everything(client, setup, outbox):
    headers, slots = setup
    tray, _, _ = menu(client)
    empty = client.post("/api/orders", json=draft(slots["pickup"]), headers=headers).json()
    res = client.post(f"/api/orders/{empty['id']}/submit", json={"version": 1}, headers=headers)
    assert res.json()["error"]["code"] == "empty_order"

    url, version = draft_with_item(client, headers, slots["pickup"], tray)
    client.patch(f"/api/admin/dishes/{tray}", json={"is_available": False}, headers=AUTH)
    res = client.post(f"{url}/submit", json={"version": version}, headers=headers)
    assert res.status_code == 409 and res.json()["error"]["details"]["dishes"] == ["חומוס"]
    client.patch(f"/api/admin/dishes/{tray}", json={"is_available": True}, headers=AUTH)

    client.post("/api/admin/blocked-dates", json={"date": EVENT_DAY.isoformat()}, headers=AUTH)
    res = client.post(f"{url}/submit", json={"version": version}, headers=headers)
    assert res.json()["error"]["code"] == "date_unavailable"
    assert client.post(f"{url}/submit", json={"version": 99}, headers=headers).status_code == 409
    assert outbox == []


def test_slot_capacity(client, setup, outbox):
    headers, slots = setup
    tray, _, _ = menu(client)
    client.patch(f"/api/admin/time-slots/{slots['pickup']}", json={"capacity": 1}, headers=AUTH)
    first, v1 = draft_with_item(client, headers, slots["pickup"], tray)
    second, v2 = draft_with_item(client, headers, slots["pickup"], tray)
    assert client.post(f"{first}/submit", json={"version": v1}, headers=headers).status_code == 200

    avail = client.get("/api/availability?from=2027-03-01&to=2027-03-31").json()
    assert avail["full_slots"] == [{"slot_id": slots["pickup"], "date": EVENT_DAY.isoformat()}]
    res = client.post(f"{second}/submit", json={"version": v2}, headers=headers)
    assert res.status_code == 409 and res.json()["error"]["code"] == "slot_full"

    # withdrawing the first frees the place
    current = client.get(first, headers=headers).json()
    res = client.post(f"{first}/withdraw", json={"version": current["version"]}, headers=headers)
    assert res.json()["status"] == "draft" and res.json()["total"] is None
    assert client.post(f"{second}/submit", json={"version": v2}, headers=headers).status_code == 200


def test_withdraw_rules_and_decision_email(client, setup, outbox):
    headers, slots = setup
    tray, _, _ = menu(client)
    url, version = draft_with_item(client, headers, slots["pickup"], tray)
    res = client.post(f"{url}/withdraw", json={"version": version}, headers=headers)
    assert res.json()["error"]["code"] == "invalid_transition"  # a draft can't be withdrawn
    submitted = client.post(f"{url}/submit", json={"version": version}, headers=headers).json()

    stranger = token(uuid.uuid4(), email="eve@example.com")
    client.put("/api/me", json={"full_name": "איב", "phone": "050-9999999"}, headers=stranger)
    body = {"version": submitted["version"]}
    assert client.post(f"{url}/withdraw", json=body, headers=stranger).status_code == 404
    assert client.post(f"{url}/submit", json=body, headers=stranger).status_code == 404

    # the owner approves first; withdrawing afterwards is refused
    approve = f"/api/admin/orders/{submitted['id']}/approve"
    assert client.post(approve, json={"note": "נתראה"}, headers=AUTH).status_code == 200
    late = client.post(f"{url}/withdraw", json=body, headers=headers)
    assert late.json()["error"]["code"] == "invalid_transition"

    decided = [e for e in outbox if e.to == "dana@example.com"]
    assert len(decided) == 1 and "אושרה" in decided[0].subject and "נתראה" in decided[0].body
    assert f"/customer/order/?order={submitted['id']}" in decided[0].body
