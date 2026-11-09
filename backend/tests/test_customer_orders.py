import uuid
from datetime import date

import pytest

from app.core import clock
from tests.conftest import AUTH, token

pytestmark = pytest.mark.usefixtures("supabase")

TODAY = date(2027, 3, 1)
EVENT_DAY = date(2027, 3, 11)
WEEKDAY = (EVENT_DAY.weekday() + 1) % 7  # Sun=0 convention


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: TODAY)


@pytest.fixture
def setup(client):
    """A customer with a profile, pickup/delivery slots and a delivery zone (רמת גן, 80);
    returns (headers, slots)."""
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
    zone = {"name": "גוש דן", "fee": "80", "cities": ["רמת גן", "תל אביב-יפו"]}
    client.post("/api/admin/delivery-zones", json=zone, headers=AUTH)
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
    body = {**body, "delivery_address": " הרצל 10 "}
    res = client.post("/api/orders", json=body, headers=headers)
    assert res.json()["error"]["code"] == "city_not_served"  # no city yet
    res = client.post("/api/orders", json={**body, "delivery_city": "חיפה"}, headers=headers)
    assert res.json()["error"]["details"]["field"] == "delivery_city"  # not in any zone
    res = client.post("/api/orders", json={**body, "delivery_city": " רמת  גן "}, headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["delivery_address"] == "הרצל 10" and res.json()["delivery_city"] == "רמת גן"


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
        delivery_city="תל אביב-יפו",
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


# --- slice 3: settings, lead time, veg + vegan, items, pricing, recommendations ---


def test_settings_defaults_and_update(client):
    assert client.get("/api/admin/settings").status_code == 401
    assert client.get("/api/admin/settings", headers=AUTH).json() == {
        "child_portion": "0.75",
        "lead_days": 3,
        "assistant_daily_limit": 30,
        "kashrut_certificate": None,
        "default_delivery_fee": None,
    }
    new = {
        "child_portion": "0.5",
        "lead_days": 5,
        "assistant_daily_limit": 10,
        "kashrut_certificate": "  כשר בהשגחת רבנות תל אביב ",
        "default_delivery_fee": "150",
    }
    res = client.put("/api/admin/settings", json=new, headers=AUTH)
    assert res.json() == {
        **new,
        "child_portion": "0.50",
        "kashrut_certificate": "כשר בהשגחת רבנות תל אביב",
        "default_delivery_fee": "150.00",
    }
    public = client.get("/api/catalog/business").json()
    assert public["kashrut_certificate"] == "כשר בהשגחת רבנות תל אביב"
    cleared = client.put(
        "/api/admin/settings", json={**new, "kashrut_certificate": ""}, headers=AUTH
    )
    assert cleared.json()["kashrut_certificate"] is None
    missing = {k: v for k, v in new.items() if k != "kashrut_certificate"}
    assert client.put("/api/admin/settings", json=missing, headers=AUTH).status_code == 422
    bad = {**new, "child_portion": "1.5"}
    assert client.put("/api/admin/settings", json=bad, headers=AUTH).status_code == 422
    negative = {**new, "default_delivery_fee": "-1"}
    assert client.put("/api/admin/settings", json=negative, headers=AUTH).status_code == 422


def test_lead_time_and_earliest_date(client, setup):
    headers, slots = setup
    avail = client.get("/api/availability?from=2027-03-01&to=2027-03-31").json()
    assert avail["earliest_date"] == "2027-03-04"  # TODAY + 3 days
    too_soon = date(2027, 3, 3)
    sunday_slot = client.post(
        "/api/admin/time-slots",
        json={"fulfillment_type": "pickup", "start_time": "10:00", "end_time": "12:00"},
        headers=AUTH,
    ).json()["id"]
    body = draft(sunday_slot, event={"event_date": too_soon.isoformat()})
    res = client.post("/api/orders", json=body, headers=headers)
    assert res.status_code == 422 and res.json()["error"]["code"] == "date_unavailable"
    client.put(
        "/api/admin/settings",
        json={
            "child_portion": "0.75",
            "lead_days": 0,
            "assistant_daily_limit": 30,
            "kashrut_certificate": None,
            "default_delivery_fee": None,
        },
        headers=AUTH,
    )
    assert client.post("/api/orders", json=body, headers=headers).status_code == 201


def test_vegetarian_and_vegan_are_separate_groups(client, setup):
    headers, slots = setup
    body = draft(slots["pickup"], event={"vegetarian_guests": 30, "vegan_guests": 21})  # 51 > 50
    res = client.post("/api/orders", json=body, headers=headers)
    assert res.status_code == 422 and res.json()["error"]["details"]["field"] == "vegan_guests"


def menu(client):
    """Two orderable dishes and one unavailable; returns their ids."""
    cat = client.post("/api/admin/categories", json={"name": "עיקריות"}, headers=AUTH).json()["id"]

    def add(name, unit, price, **extra):
        body = {"category_id": cat, "name": name, "pricing_unit": unit, "unit_price": price}
        return client.post("/api/admin/dishes", json={**body, **extra}, headers=AUTH).json()["id"]

    tray = add("חומוס", "per_tray", "120", serves_adults="10", min_quantity="2")
    kg = add("בריסקט", "per_weight", "219.99", serves_adults="4")
    off = add("טופו", "per_guest", "48", is_available=False)
    client.put(f"/api/admin/dishes/{tray}/dietary", json={"is_vegan": True}, headers=AUTH)
    return tray, kg, off


def test_items_pricing_and_versions(client, setup):
    headers, slots = setup
    tray, kg, off = menu(client)
    order = client.post("/api/orders", json=draft(slots["pickup"]), headers=headers).json()
    url = f"/api/orders/{order['id']}/items"

    res = client.put(f"{url}/{tray}", json={"quantity": "3", "version": 1}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["version"] == 2 and res.json()["items"] == [
        {"dish_id": tray, "quantity": "3.00"}
    ]
    res = client.put(f"{url}/{kg}", json={"quantity": "2.5", "version": 2}, headers=headers)
    assert res.json()["version"] == 3

    pricing = client.get(f"/api/orders/{order['id']}/pricing", headers=headers).json()
    assert pricing["vat_included"] is True and pricing["currency"] == "ILS"
    assert [(line["name"], line["line_total"]) for line in pricing["lines"]] == [
        ("בריסקט", "549.98"),
        ("חומוס", "360.00"),
    ]
    assert pricing["subtotal"] == "909.98" and pricing["total"] == "909.98"

    stale = client.put(f"{url}/{tray}", json={"quantity": "4", "version": 2}, headers=headers)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "order_version_conflict"
    res = client.delete(f"{url}/{kg}?version=3", headers=headers)
    assert res.json()["version"] == 4 and len(res.json()["items"]) == 1
    assert client.delete(f"{url}/{kg}?version=4", headers=headers).status_code == 404


@pytest.mark.parametrize(
    ("dish", "quantity", "code"),
    [
        ("tray", "1.5", "validation_error"),  # whole trays only
        ("tray", "1", "below_minimum"),  # minimum 2
        ("kg", "2.3", "validation_error"),  # 0.5 kg steps
        ("off", "10", "dish_unavailable"),
    ],
)
def test_item_rules(client, setup, dish, quantity, code):
    headers, slots = setup
    ids = dict(zip(("tray", "kg", "off"), menu(client), strict=True))
    order = client.post("/api/orders", json=draft(slots["pickup"]), headers=headers).json()
    res = client.put(
        f"/api/orders/{order['id']}/items/{ids[dish]}",
        json={"quantity": quantity, "version": 1},
        headers=headers,
    )
    assert res.status_code == 422 and res.json()["error"]["code"] == code, res.text


def test_items_owner_only_and_draft_only(client, setup, make_session):
    from app.models.orders import Order

    headers, slots = setup
    tray, _, _ = menu(client)
    order = client.post("/api/orders", json=draft(slots["pickup"]), headers=headers).json()
    url = f"/api/orders/{order['id']}"
    stranger = token(uuid.uuid4(), email="eve@example.com")
    client.put("/api/me", json={"full_name": "איב", "phone": "050-9999999"}, headers=stranger)
    body = {"quantity": "2", "version": 1}
    assert client.put(f"{url}/items/{tray}", json=body, headers=stranger).status_code == 404
    assert client.get(f"{url}/pricing", headers=stranger).status_code == 404
    assert client.get(f"{url}/recommendations", headers=stranger).status_code == 404
    with make_session() as db:
        db.get(Order, uuid.UUID(order["id"])).status = "pending_approval"
        db.commit()
    res = client.put(f"{url}/items/{tray}", json=body, headers=headers)
    assert res.json()["error"]["code"] == "invalid_transition"


def test_recommendations_endpoint(client, setup):
    headers, slots = setup
    tray, kg, _ = menu(client)
    # 40 adults + 10 children, 5 vegetarian, 2 vegan -> 47.5 portions
    order = client.post("/api/orders", json=draft(slots["pickup"]), headers=headers).json()
    recs = client.get(f"/api/orders/{order['id']}/recommendations", headers=headers).json()
    by_dish = {r["dish_id"]: (r["quantity"], r["eligible_guests"]) for r in recs}
    # hummus is vegan (everyone, 47.5/10 -> 5); brisket's dietary is unknown -> 43 guests,
    # 40.85/4 = 10.21 -> 10.5 kg; the unavailable dish never appears
    assert by_dish == {tray: ("5.00", 50), kg: ("10.50", 43)}
