"""Alcohol, sold to 18+ only (OPEN_DECISIONS #11)."""

import pytest

from tests.conftest import AUTH
from tests.test_customer_orders import fixed_today, menu, setup  # noqa: F401
from tests.test_submit import draft_with_item, outbox  # noqa: F401

pytestmark = pytest.mark.usefixtures("supabase")


def wine(client, kg):
    res = client.patch(f"/api/admin/dishes/{kg}", json={"contains_alcohol": True}, headers=AUTH)
    assert res.status_code == 200 and res.json()["contains_alcohol"] is True


def test_dish_alcohol_flag(client):
    tray, kg, _ = menu(client)
    assert client.get(f"/api/catalog/dishes/{tray}").json()["contains_alcohol"] is False
    wine(client, kg)
    assert client.get(f"/api/catalog/dishes/{kg}").json()["contains_alcohol"] is True
    res = client.patch(f"/api/admin/dishes/{kg}", json={"contains_alcohol": None}, headers=AUTH)
    assert res.status_code == 422


def test_submit_with_alcohol_needs_age_confirmation(client, setup, outbox):
    headers, slots = setup
    tray, kg, _ = menu(client)
    wine(client, kg)
    url, version = draft_with_item(client, headers, slots["pickup"], kg, quantity="2")

    res = client.post(f"{url}/submit", json={"version": version}, headers=headers)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "age_confirmation_required"
    assert not outbox

    body = {"version": version, "adult_confirmed": True}
    order = client.post(f"{url}/submit", json=body, headers=headers).json()
    assert order["status"] == "pending_approval" and order["adult_confirmed_at"]
    detail = client.get(f"/api/admin/orders/{order['id']}", headers=AUTH).json()
    assert detail["adult_confirmed_at"]
    assert "תעודה מזהה" in outbox[0].body

    # withdrawing clears it; the next submit asks again
    order = client.post(f"{url}/withdraw", json={"version": order["version"]}, headers=headers)
    assert order.json()["adult_confirmed_at"] is None


def test_order_without_alcohol_needs_no_confirmation(client, setup, outbox):
    headers, slots = setup
    tray, kg, _ = menu(client)
    wine(client, kg)
    url, version = draft_with_item(client, headers, slots["pickup"], tray)
    order = client.post(f"{url}/submit", json={"version": version}, headers=headers).json()
    assert order["status"] == "pending_approval" and order["adult_confirmed_at"] is None
    assert "תעודה מזהה" not in outbox[0].body

    # the owner can't add alcohol to an order whose customer never confirmed 18+
    body = {"items": [{"dish_id": tray, "quantity": "3"}, {"dish_id": kg, "quantity": "1"}]}
    admin = f"/api/admin/orders/{order['id']}/proposals"
    res = client.post(admin, json=body, headers=AUTH)
    assert res.json()["error"]["code"] == "age_confirmation_required"

    # a dish marked alcohol after submission doesn't block proposals that keep it as is
    client.patch(f"/api/admin/dishes/{tray}", json={"contains_alcohol": True}, headers=AUTH)
    res = client.post(admin, json={"items": [{"dish_id": tray, "quantity": "4"}]}, headers=AUTH)
    assert res.status_code == 201, res.text
