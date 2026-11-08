"""Phase 3 slice 5: delivery zones by city list (OPEN_DECISIONS #19)."""

import pytest

from tests.conftest import AUTH
from tests.test_customer_orders import draft, fixed_today, menu, setup  # noqa: F401
from tests.test_submit import outbox  # noqa: F401

pytestmark = pytest.mark.usefixtures("supabase")
ZONES = "/api/admin/delivery-zones"


def zones(client):
    return {z["name"]: z for z in client.get(ZONES, headers=AUTH).json()}


def test_zone_admin(client):
    assert client.get(ZONES).status_code == 401
    body = {"name": "השרון", "fee": "120", "cities": ["הרצליה", " רעננה ", "רעננה"]}
    res = client.post(ZONES, json=body, headers=AUTH)
    assert res.status_code == 201, res.text
    zone = res.json()
    assert zone["cities"] == ["הרצליה", "רעננה"] and zone["fee"] == "120.00"  # trimmed, deduped

    other = {"name": "מרכז", "fee": "90", "cities": ["כפר סבא", "רעננה"]}
    res = client.post(ZONES, json=other, headers=AUTH)
    assert res.status_code == 409
    assert res.json()["error"]["details"] == {"city": "רעננה", "zone": "השרון"}

    # editing a zone may keep its own cities; replacing the list frees the old ones
    url = f"{ZONES}/{zone['id']}"
    res = client.patch(url, json={"cities": ["רעננה", "כפר סבא"], "fee": "100"}, headers=AUTH)
    assert res.json()["cities"] == ["כפר סבא", "רעננה"] and res.json()["fee"] == "100.00"
    assert client.post(ZONES, json={**other, "cities": ["הרצליה"]}, headers=AUTH).status_code == 201
    assert client.patch(url, json={"fee": "-1"}, headers=AUTH).status_code == 422
    assert client.patch(url, json={"name": None}, headers=AUTH).status_code == 422
    assert (
        client.post(ZONES, json={**body, "name": "x", "cities": []}, headers=AUTH).status_code
        == 422
    )

    client.patch(url, json={"is_active": False}, headers=AUTH)
    assert [c["city"] for c in client.get("/api/delivery/cities").json()] == ["הרצליה"]
    assert client.delete(url, headers=AUTH).status_code == 204
    assert set(zones(client)) == {"מרכז"}


def delivery_order(client, headers, slots, tray):
    body = draft(
        slots["delivery_any_day"],
        fulfillment_type="delivery",
        delivery_address="הרצל 10",
        delivery_city="רמת גן",
    )
    order = client.post("/api/orders", json=body, headers=headers).json()
    url = f"/api/orders/{order['id']}"
    item = {"quantity": "3", "version": 1}
    version = client.put(f"{url}/items/{tray}", json=item, headers=headers).json()["version"]
    return url, version


def test_fee_is_live_while_draft_and_frozen_at_submit(client, setup, outbox):
    headers, slots = setup
    tray, _, _ = menu(client)
    url, version = delivery_order(client, headers, slots, tray)
    zone = zones(client)["גוש דן"]

    pricing = client.get(f"{url}/pricing", headers=headers).json()
    assert (pricing["subtotal"], pricing["delivery_fee"], pricing["total"]) == (
        "360.00",
        "80.00",
        "440.00",
    )
    client.patch(f"{ZONES}/{zone['id']}", json={"fee": "95"}, headers=AUTH)
    assert client.get(f"{url}/pricing", headers=headers).json()["total"] == "455.00"  # live

    order = client.post(f"{url}/submit", json={"version": version}, headers=headers).json()
    assert (order["delivery_fee"], order["total"]) == ("95.00", "455.00")
    assert "כולל משלוח 95.00" in outbox[0].body and "הרצל 10, רמת גן" in outbox[0].body

    # after submission the owner changes or deletes the zone: the order keeps its fee
    client.patch(f"{ZONES}/{zone['id']}", json={"fee": "200"}, headers=AUTH)
    client.delete(f"{ZONES}/{zone['id']}", headers=AUTH)
    assert client.get(f"{url}/pricing", headers=headers).json()["total"] == "455.00"
    detail = client.get(f"/api/admin/orders/{order['id']}", headers=AUTH).json()
    assert detail["delivery_fee"] == "95.00" and detail["delivery_city"] == "רמת גן"


def test_unserved_city_blocks_submit_and_withdraw_unfreezes(client, setup, outbox):
    headers, slots = setup
    tray, _, _ = menu(client)
    url, version = delivery_order(client, headers, slots, tray)
    zone = zones(client)["גוש דן"]

    client.patch(f"{ZONES}/{zone['id']}", json={"is_active": False}, headers=AUTH)
    pricing = client.get(f"{url}/pricing", headers=headers).json()
    assert pricing["delivery_fee"] is None  # no active zone for the city right now
    res = client.post(f"{url}/submit", json={"version": version}, headers=headers)
    assert res.json()["error"]["code"] == "city_not_served"

    client.patch(f"{ZONES}/{zone['id']}", json={"is_active": True}, headers=AUTH)
    order = client.post(f"{url}/submit", json={"version": version}, headers=headers).json()
    assert order["delivery_fee"] == "80.00"
    client.patch(f"{ZONES}/{zone['id']}", json={"fee": "60"}, headers=AUTH)
    back = client.post(f"{url}/withdraw", json={"version": order["version"]}, headers=headers)
    assert back.json()["delivery_fee"] is None  # unfrozen
    assert client.get(f"{url}/pricing", headers=headers).json()["delivery_fee"] == "60.00"


def test_pickup_has_no_fee_or_city(client, setup):
    headers, slots = setup
    tray, _, _ = menu(client)
    body = draft(slots["pickup"], delivery_address="ignored", delivery_city="רמת גן")
    order = client.post("/api/orders", json=body, headers=headers).json()
    assert order["delivery_city"] is None and order["delivery_address"] is None
    url = f"/api/orders/{order['id']}"
    client.put(f"{url}/items/{tray}", json={"quantity": "2", "version": 1}, headers=headers)
    pricing = client.get(f"{url}/pricing", headers=headers).json()
    assert pricing["delivery_fee"] is None and pricing["total"] == "240.00"


def default_fee(client, fee):
    settings = client.get("/api/admin/settings", headers=AUTH).json()
    body = {**settings, "default_delivery_fee": fee}
    assert client.put("/api/admin/settings", json=body, headers=AUTH).status_code == 200


def test_default_fee_delivers_to_any_israeli_locality(client, setup, outbox):
    headers, slots = setup
    tray, _, _ = menu(client)
    body = draft(
        slots["delivery_any_day"],
        fulfillment_type="delivery",
        delivery_address="הרצל 10",
        delivery_city="באר  שבע",
    )
    # no default fee: only zone cities are served, as before
    res = client.post("/api/orders", json=body, headers=headers)
    assert res.json()["error"]["code"] == "city_not_served"
    assert "באר שבע" not in [c["city"] for c in client.get("/api/delivery/cities").json()]

    default_fee(client, "150")
    cities = {c["city"]: c["fee"] for c in client.get("/api/delivery/cities").json()}
    assert cities["רמת גן"] == "80.00" and cities["באר שבע"] == "150.00"
    assert "קרית אונו" in cities and len(cities) > 1000  # every CBS locality
    assert list(cities).count("רמת גן") == 1  # a zone city isn't listed twice

    res = client.post("/api/orders", json=body, headers=headers)
    assert res.status_code == 201, res.text
    order = res.json()
    assert order["delivery_city"] == "באר שבע"
    url = f"/api/orders/{order['id']}"
    item = {"quantity": "3", "version": 1}
    version = client.put(f"{url}/items/{tray}", json=item, headers=headers).json()["version"]
    assert client.get(f"{url}/pricing", headers=headers).json()["delivery_fee"] == "150.00"
    submitted = client.post(f"{url}/submit", json={"version": version}, headers=headers).json()
    assert submitted["delivery_fee"] == "150.00"  # frozen like a zone fee

    # another spelling of a CBS name is stored in the CBS spelling
    other = {**body, "delivery_city": "קריית  אונו"}
    stored = client.post("/api/orders", json=other, headers=headers).json()["delivery_city"]
    assert stored == "קרית אונו"
    # a zone city keeps the zone fee, and a made-up name is still refused
    zone_body = {**body, "delivery_city": "רמת גן"}
    zone_city = client.post("/api/orders", json=zone_body, headers=headers)
    assert zone_city.json()["delivery_city"] == "רמת גן"
    made_up = {**body, "delivery_city": "עיר שלא קיימת"}
    res = client.post("/api/orders", json=made_up, headers=headers)
    assert res.json()["error"]["code"] == "city_not_served"
