"""Phase 3 slice 6: owner change proposals (OPEN_DECISIONS #6)."""

import uuid

import pytest

from tests.conftest import AUTH, token
from tests.test_customer_orders import fixed_today, menu, setup  # noqa: F401
from tests.test_submit import draft_with_item, outbox  # noqa: F401

pytestmark = pytest.mark.usefixtures("supabase")


@pytest.fixture
def submitted(client, setup, outbox):
    """A submitted order with 3 trays of hummus (120 each); returns ids and urls."""
    headers, slots = setup
    tray, kg, off = menu(client)
    url, version = draft_with_item(client, headers, slots["pickup"], tray)
    order = client.post(f"{url}/submit", json={"version": version}, headers=headers).json()
    outbox.clear()
    return {
        "headers": headers,
        "order": order,
        "url": url,
        "admin": f"/api/admin/orders/{order['id']}",
        "tray": tray,
        "kg": kg,
        "off": off,
    }


def propose(client, s, items, note="הגדלנו את החומוס"):
    body = {"items": items, "note": note}
    return client.post(f"{s['admin']}/proposals", json=body, headers=AUTH)


def test_owner_proposes_with_frozen_prices(client, submitted, outbox):
    s = submitted
    # the catalog price of hummus changes after submission: existing lines keep 120
    client.patch(f"/api/admin/dishes/{s['tray']}", json={"unit_price": "999"}, headers=AUTH)
    res = propose(
        client,
        s,
        [
            {"dish_id": s["tray"], "quantity": "5"},
            {"dish_id": s["kg"], "quantity": "2.5"},  # added at today's catalog price 219.99
        ],
    )
    assert res.status_code == 201, res.text
    p = res.json()
    assert p["status"] == "pending" and p["proposed_by"] == "owner"
    assert {(c["op"], c["name"], c["from_quantity"], c["to_quantity"]) for c in p["changes"]} == {
        ("set_quantity", "חומוס", "3.00", "5"),
        ("add_item", "בריסקט", None, "2.5"),
    }
    assert [(line["name"], line["line_total"]) for line in p["lines"]] == [
        ("בריסקט", "549.98"),
        ("חומוס", "600.00"),
    ]
    assert (p["price_before"], p["price_after"]) == ("360.00", "1149.98")
    assert [e.kind for e in outbox] == ["proposal_created"]
    assert outbox[0].to == "dana@example.com" and "1,149.98" in outbox[0].body
    assert "\n- " in outbox[0].body  # real line breaks between the listed changes


def test_one_open_proposal_and_owner_cannot_decide_meanwhile(client, submitted):
    s = submitted
    p = propose(client, s, [{"dish_id": s["tray"], "quantity": "4"}]).json()
    again = propose(client, s, [{"dish_id": s["tray"], "quantity": "6"}])
    assert again.status_code == 409 and again.json()["error"]["code"] == "proposal_pending"
    blocked = client.post(f"{s['admin']}/approve", headers=AUTH)
    assert blocked.json()["error"]["code"] == "proposal_pending"

    cancelled = client.post(f"{s['admin']}/proposals/{p['id']}/cancel", headers=AUTH)
    assert cancelled.json()["status"] == "cancelled"
    assert client.post(f"{s['admin']}/approve", headers=AUTH).status_code == 200


def test_accept_applies_and_approves(client, submitted, outbox):
    s = submitted
    p = propose(client, s, [{"dish_id": s["kg"], "quantity": "2"}]).json()  # hummus removed
    assert [c["op"] for c in p["changes"]] == ["add_item", "remove_item"]

    listed = client.get(f"{s['url']}/proposals", headers=s["headers"]).json()
    assert [x["id"] for x in listed] == [p["id"]]
    res = client.post(f"{s['url']}/proposals/{p['id']}/accept", headers=s["headers"])
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "accepted"

    order = client.get(s["url"], headers=s["headers"]).json()
    assert order["status"] == "approved" and order["total"] == "439.98"
    assert order["decision_note"] == "הגדלנו את החומוס"
    assert order["items"] == [{"dish_id": s["kg"], "quantity": "2.00"}]
    pricing = client.get(f"{s['url']}/pricing", headers=s["headers"]).json()
    assert [(line["name"], line["line_total"]) for line in pricing["lines"]] == [
        ("בריסקט", "439.98")
    ]
    assert [e.kind for e in outbox] == ["proposal_created", "proposal_answered"]
    assert "אישר" in outbox[1].subject and outbox[1].to == "owner@example.com"
    again = client.post(f"{s['url']}/proposals/{p['id']}/accept", headers=s["headers"])
    assert again.json()["error"]["code"] == "proposal_not_pending"


def test_decline_keeps_order_for_the_owner(client, submitted, outbox):
    s = submitted
    p = propose(client, s, [{"dish_id": s["tray"], "quantity": "6"}]).json()
    res = client.post(
        f"{s['url']}/proposals/{p['id']}/decline", json={"note": "יקר לנו"}, headers=s["headers"]
    )
    assert res.json()["status"] == "declined" and res.json()["customer_note"] == "יקר לנו"
    order = client.get(s["url"], headers=s["headers"]).json()
    assert order["status"] == "pending_approval" and order["total"] == "360.00"
    assert "יקר לנו" in outbox[-1].body
    assert client.post(f"{s['admin']}/approve", headers=AUTH).status_code == 200  # owner decides


def test_withdraw_expires_the_open_proposal(client, submitted):
    s = submitted
    p = propose(client, s, [{"dish_id": s["tray"], "quantity": "4"}]).json()
    version = client.get(s["url"], headers=s["headers"]).json()["version"]
    client.post(f"{s['url']}/withdraw", json={"version": version}, headers=s["headers"])
    proposals = client.get(f"{s['admin']}/proposals", headers=AUTH)
    assert proposals.status_code == 404  # the order is a draft again: hidden from the owner
    listed = client.get(f"{s['url']}/proposals", headers=s["headers"]).json()
    assert listed[0]["status"] == "expired"
    res = client.post(f"{s['url']}/proposals/{p['id']}/accept", headers=s["headers"])
    assert res.json()["error"]["code"] == "proposal_not_pending"


def test_rules_and_isolation(client, submitted):
    s = submitted
    same = propose(client, s, [{"dish_id": s["tray"], "quantity": "3"}])
    assert same.json()["error"]["code"] == "no_changes"
    unavailable = propose(client, s, [{"dish_id": s["off"], "quantity": "10"}])
    assert unavailable.json()["error"]["code"] == "dish_unavailable"
    below_min = propose(client, s, [{"dish_id": s["tray"], "quantity": "1"}])
    assert below_min.json()["error"]["code"] == "below_minimum"
    half_tray = propose(client, s, [{"dish_id": s["tray"], "quantity": "2.5"}])
    assert half_tray.status_code == 422
    twice = propose(client, s, [{"dish_id": s["tray"], "quantity": "4"}] * 2)
    assert twice.status_code == 422
    assert (
        client.post(f"{s['admin']}/proposals", json={"items": []}, headers=AUTH).status_code == 422
    )
    assert client.post(f"{s['admin']}/proposals", json={"items": []}).status_code == 401

    p = propose(client, s, [{"dish_id": s["tray"], "quantity": "4"}]).json()
    stranger = token(uuid.uuid4(), email="eve@example.com")
    client.put("/api/me", json={"full_name": "איב", "phone": "050-9999999"}, headers=stranger)
    assert client.get(f"{s['url']}/proposals", headers=stranger).status_code == 404
    assert (
        client.post(f"{s['url']}/proposals/{p['id']}/accept", headers=stranger).status_code == 404
    )
    unknown = client.post(f"{s['url']}/proposals/{uuid.uuid4()}/accept", headers=s["headers"])
    assert unknown.status_code == 404

    mine = client.get("/api/me/orders", headers=s["headers"]).json()
    assert mine[0]["has_pending_proposal"] is True
