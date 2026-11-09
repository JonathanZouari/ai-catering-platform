import pytest
from test_orders import ADMIN, EVENT_DAY, Shop

ORDERS = f"{ADMIN}/orders"


@pytest.fixture
def shop(client, make_tenant):
    return Shop(client, make_tenant("caterer-a"))


@pytest.fixture
def other_shop(client, make_tenant):
    return Shop(client, make_tenant("caterer-b"))


def submitted(shop, **overrides):
    order = shop.order(**overrides)
    order.add(shop.meat, "2")
    order.store(order.submit())
    return order


def get(shop, path=""):
    return shop.client.get(f"{ORDERS}{path}", headers=shop.headers)


def decide(shop, order, action, **body):
    fields = {"version": order.data["version"]} | body
    url = f"{ORDERS}/{order.data['id']}/{action}"
    return shop.client.post(url, json=fields, headers=shop.headers)


def code(response):
    return response.status_code, response.json()["error"]["code"]


def test_list_shows_submitted_orders_but_not_drafts(shop):
    shop.order()
    order = submitted(shop)

    rows = get(shop).json()

    assert [row["id"] for row in rows] == [order.data["id"]]
    assert rows[0]["customer_name"] == "דנה לוי"
    assert rows[0]["guests"] == 25
    assert rows[0]["total"] == "200.00"
    assert "token" not in str(rows[0])


def test_draft_can_not_be_opened_or_decided(shop):
    order = shop.order()
    assert get(shop, f"/{order.data['id']}").status_code == 404
    assert code(decide(shop, order, "approve")) == (409, "invalid_transition")


def test_list_filters_by_status(shop):
    approved = submitted(shop)
    waiting = submitted(shop)
    assert decide(shop, approved, "approve").status_code == 200

    pending = get(shop, "?status=pending_approval").json()
    assert [row["id"] for row in pending] == [waiting.data["id"]]
    assert get(shop, "?status=draft").json() == []


def test_list_is_soonest_event_first(shop):
    later = submitted(shop)
    event = later.data["event"] | {"event_date": EVENT_DAY.replace(day=14).isoformat()}
    details = {"customer": {"full_name": "דנה לוי", "phone": "050-1234567"}, "event": event}
    late = shop.order(**details)
    late.add(shop.meat)
    late.store(late.submit())

    rows = get(shop).json()
    assert [row["id"] for row in rows] == [later.data["id"], late.data["id"]]


def test_detail_shows_frozen_order_and_warning_acknowledgement(shop):
    order = shop.order()
    order.add(shop.meat, "1")
    order.add(shop.dairy, "1")
    order.store(order.submit(acknowledge_kashrut_warning=True))
    shop.patch(f"dishes/{shop.meat['id']}", {"unit_price": "999.00", "name": "שונה"})

    body = get(shop, f"/{order.data['id']}").json()

    assert body["kashrut_warning_acknowledged"] is True
    assert body["submitted_at"] is not None
    assert body["decided_at"] is None
    assert body["total"] == "180.00"
    assert {line["name"] for line in body["lines"]} == {"עוף", "לזניה"}
    assert body["customer"]["phone"] == "050-1234567"


def test_dish_on_a_submitted_order_can_not_be_deleted(shop):
    submitted(shop)
    response = shop.client.delete(f"{ADMIN}/dishes/{shop.meat['id']}", headers=shop.headers)
    assert response.status_code == 409


def test_approve_records_the_decision_and_reaches_the_customer(shop):
    order = submitted(shop)

    response = decide(shop, order, "approve", note="  נתראה באירוע  ")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["decided_at"] is not None
    assert body["version"] == order.data["version"] + 1

    seen = shop.client.get(order.url, headers=order.headers).json()
    assert seen["status"] == "approved"
    assert seen["decision_note"] == "נתראה באירוע"


def test_approve_note_is_optional_and_blank_is_stored_as_none(shop):
    assert decide(shop, submitted(shop), "approve").json()["decision_note"] is None
    assert decide(shop, submitted(shop), "approve", note="   ").json()["decision_note"] is None


def test_reject_records_the_note_and_reaches_the_customer(shop):
    order = submitted(shop)

    assert decide(shop, order, "reject", note="התאריך תפוס").json()["status"] == "rejected"

    seen = shop.client.get(order.url, headers=order.headers).json()
    assert seen["status"] == "rejected"
    assert seen["decision_note"] == "התאריך תפוס"


@pytest.mark.parametrize("body", [{}, {"note": ""}, {"note": "   "}, {"note": None}])
def test_reject_needs_a_note(shop, body):
    order = submitted(shop)
    assert decide(shop, order, "reject", **body).status_code == 422
    assert get(shop, f"/{order.data['id']}").json()["status"] == "pending_approval"


def test_note_length_is_limited(shop):
    assert decide(shop, submitted(shop), "approve", note="א" * 1001).status_code == 422


def test_decision_body_cannot_set_other_fields(shop):
    order = submitted(shop)
    assert decide(shop, order, "approve", total="1.00").status_code == 422
    assert decide(shop, order, "approve", caterer_id=str(shop.tenant.id)).status_code == 422


@pytest.mark.parametrize(
    ("first", "second"),
    [("approve", "approve"), ("approve", "reject"), ("reject", "approve")],
)
def test_order_can_only_be_decided_once(shop, first, second):
    order = submitted(shop)
    response = decide(shop, order, first, note="הערה")
    assert response.status_code == 200
    order.data = response.json()
    assert code(decide(shop, order, second, note="הערה")) == (409, "invalid_transition")


def test_stale_version_is_refused(shop):
    order = submitted(shop)
    body = {"version": order.data["version"] - 1}
    url = f"{ORDERS}/{order.data['id']}/approve"
    response = shop.client.post(url, json=body, headers=shop.headers)
    assert code(response) == (409, "order_version_conflict")


def test_approved_order_keeps_the_slot(shop):
    shop.patch(f"time-slots/{shop.slot['id']}", {"capacity": 1})
    first = submitted(shop)
    second = shop.order()
    second.add(shop.meat)
    assert code(second.submit()) == (409, "slot_full")

    decide(shop, first, "approve")
    assert code(second.submit()) == (409, "slot_full")


def test_rejecting_frees_the_slot(shop):
    shop.patch(f"time-slots/{shop.slot['id']}", {"capacity": 1})
    first = submitted(shop)
    second = shop.order()
    second.add(shop.meat)

    decide(shop, first, "reject", note="לא פנוי")

    assert second.submit().status_code == 200


def test_customer_can_not_edit_a_decided_order(shop):
    order = submitted(shop)
    order.data = decide(shop, order, "approve").json()
    url = f"{order.url}/items/{shop.dairy['id']}"
    body = {"quantity": "1", "version": order.data["version"]}
    response = shop.client.put(url, json=body, headers=order.headers)
    assert code(response) == (409, "invalid_transition")


def test_another_caterers_order_looks_missing(shop, other_shop):
    order = submitted(shop)
    order_id = order.data["id"]

    assert get(other_shop).json() == []
    assert get(other_shop, f"/{order_id}").status_code == 404
    assert decide(other_shop, order, "approve").status_code == 404
    assert decide(other_shop, order, "reject", note="לא").status_code == 404
    assert get(shop, f"/{order_id}").json()["status"] == "pending_approval"


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_customer_token_can_not_decide(shop, action):
    order = submitted(shop)
    url = f"{ORDERS}/{order.data['id']}/{action}"
    body = {"version": order.data["version"], "note": "מאושר"}

    assert shop.client.post(url, json=body).status_code == 401
    response = shop.client.post(url, json=body, headers=order.headers)
    assert response.status_code == 401
    bearer = {"Authorization": f"Bearer {order.token}"}
    assert shop.client.post(url, json=body, headers=bearer).status_code == 401


def test_customer_routes_offer_no_way_to_decide(shop):
    order = submitted(shop)
    for action in ("approve", "reject"):
        response = shop.client.post(f"{order.url}/{action}", json={}, headers=order.headers)
        assert response.status_code in (404, 405)


def test_customer_sees_the_caterers_phone_on_the_public_profile(shop):
    shop.patch("profile", {"contact_phone": "03-1234567"})
    public = shop.client.get(f"/api/c/{shop.tenant.slug}").json()
    assert public["contact_phone"] == "03-1234567"
