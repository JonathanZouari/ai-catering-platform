from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.models.enums import CategoryType, KashrutClass, KashrutMixingRule, PricingUnit
from app.services import availability, kashrut, pricing, quantities

ADMIN = "/api/admin"
EVENT_DAY = date(2031, 1, 7)  # A Tuesday, far enough ahead to stay in the future.
TUESDAY = (EVENT_DAY.weekday() + 1) % 7


def customer_details(slot_id, **overrides):
    return {
        "customer": {"full_name": "דנה לוי", "phone": "050-1234567"},
        "event": {
            "event_type": "יום הולדת",
            "event_date": EVENT_DAY.isoformat(),
            "adults": 20,
            "children": 5,
            "vegetarian_guests": 3,
            "vegan_guests": 2,
        },
        "fulfillment_type": "pickup",
        "time_slot_id": slot_id,
    } | overrides


class CustomerOrder:
    def __init__(self, client, created):
        self.client = client
        self.token = created["token"]
        self.data = created["order"]
        self.url = f"/api/orders/{self.data['id']}"
        self.headers = {"X-Order-Token": self.token}

    def store(self, response):
        assert response.status_code == 200, response.text
        self.data = response.json()
        return self.data

    def add(self, dish, quantity="2"):
        body = {"quantity": quantity, "version": self.data["version"]}
        url = f"{self.url}/items/{dish['id']}"
        return self.store(self.client.put(url, json=body, headers=self.headers))

    def submit(self, **fields):
        body = {"version": self.data["version"]} | fields
        return self.client.post(f"{self.url}/submit", json=body, headers=self.headers)

    def error(self, response):
        return response.status_code, response.json()["error"]["code"]


class Shop:
    """A caterer with a menu, ready for customers."""

    def __init__(self, client, tenant):
        self.client, self.tenant = client, tenant
        self.headers = tenant.headers
        self.category = self.post("categories", {"name": "עיקריות", "category_type": "main"})
        self.meat = self.dish("עוף", "100.00", "meat", servings_per_unit="10")
        self.dairy = self.dish("לזניה", "80.00", "dairy", servings_per_unit="8")
        pickup = {
            "fulfillment_type": "pickup",
            "weekday": TUESDAY,
            "start_time": "09:00",
            "end_time": "12:00",
        }
        delivery = {"fulfillment_type": "delivery", "start_time": "13:00", "end_time": "15:00"}
        self.slot = self.post("time-slots", pickup)
        self.delivery_slot = self.post("time-slots", delivery)
        self.post("delivery-zones", {"name": "מרכז", "fee": "50.00", "cities": ["חיפה"]})

    def post(self, path, body):
        response = self.client.post(f"{ADMIN}/{path}", json=body, headers=self.headers)
        assert response.status_code == 201, response.text
        return response.json()

    def patch(self, path, body):
        response = self.client.patch(f"{ADMIN}/{path}", json=body, headers=self.headers)
        assert response.status_code == 200, response.text

    def dish(self, name, price, kashrut_class, category=None, **fields):
        body = {
            "category_id": (category or self.category)["id"],
            "name": name,
            "pricing_unit": "per_tray",
            "unit_price": price,
        } | fields
        dish = self.post("dishes", body)
        url = f"{ADMIN}/dishes/{dish['id']}/dietary"
        self.client.put(url, json={"kashrut_class": kashrut_class}, headers=self.headers)
        return dish

    def create(self, details):
        return self.client.post(f"/api/c/{self.tenant.slug}/orders", json=details)

    def order(self, **overrides):
        response = self.create(customer_details(self.slot["id"], **overrides))
        assert response.status_code == 201, response.text
        return CustomerOrder(self.client, response.json())


@pytest.fixture
def shop(client, make_tenant):
    return Shop(client, make_tenant("caterer-a"))


# Pure logic


def test_line_total_rounds_half_up():
    assert pricing.line_total(Decimal("10.01"), Decimal("0.5")) == Decimal("5.01")
    assert pricing.line_total(Decimal("33.33"), Decimal("3")) == Decimal("99.99")


def test_order_total_adds_delivery_without_a_vat_line():
    subtotal, total = pricing.order_total([Decimal("10.10"), Decimal("20.20")], Decimal("50"))
    assert (subtotal, total) == (Decimal("30.30"), Decimal("80.30"))


def _dish(**fields):
    category = SimpleNamespace(category_type=fields.pop("type", CategoryType.MAIN))
    defaults = {
        "id": uuid4(),
        "category": category,
        "dietary": None,
        "pricing_unit": PricingUnit.PER_TRAY,
        "servings_per_unit": Decimal(10),
        "min_quantity": None,
    }
    return SimpleNamespace(**(defaults | fields))


def _diet(kashrut_class=KashrutClass.PAREVE, vegan=None, vegetarian=None):
    return SimpleNamespace(kashrut_class=kashrut_class, is_vegan=vegan, is_vegetarian=vegetarian)


def _rule(adult, child):
    return SimpleNamespace(portions_per_adult=Decimal(adult), portions_per_child=Decimal(child))


RULES = {CategoryType.MAIN: _rule("1", "0.5"), CategoryType.OTHER: _rule("0", "0")}
EVENT = SimpleNamespace(adults=20, children=4, vegetarian_guests=0, vegan_guests=0)
VEGAN = _diet(vegan=True, vegetarian=True)


def test_recommendation_rounds_up_to_whole_trays():
    dish = _dish(dietary=VEGAN)
    assert quantities.recommend([dish], EVENT, RULES)[dish.id] == 3  # 22 portions / 10.


def test_recommendation_splits_across_dishes_in_a_category():
    a, b = _dish(dietary=VEGAN), _dish(dietary=VEGAN)
    result = quantities.recommend([a, b], EVENT, RULES)
    assert result[a.id] == result[b.id] == 2  # 11 portions each.


def test_no_servings_or_no_rule_means_no_recommendation():
    unknown = _dish(servings_per_unit=None)
    other = _dish(type=CategoryType.OTHER)
    assert quantities.recommend([unknown], EVENT, RULES)[unknown.id] is None
    assert quantities.recommend([other], EVENT, RULES)[other.id] is None


def test_diets_exclude_guests_who_cannot_eat_the_dish():
    event = SimpleNamespace(adults=20, children=0, vegetarian_guests=5, vegan_guests=5)
    meat = _dish(dietary=_diet(KashrutClass.MEAT))
    assert quantities.recommend([meat], event, RULES)[meat.id] == 1  # 10 of 20 eligible.
    vegetarian = _dish(dietary=_diet(KashrutClass.DAIRY, vegan=False, vegetarian=True))
    assert quantities.recommend([vegetarian], event, RULES)[vegetarian.id] == 2  # 15 of 20.


def test_unknown_diet_counts_as_not_suitable_for_vegetarians():
    event = SimpleNamespace(adults=20, children=0, vegetarian_guests=10, vegan_guests=0)
    dish = _dish(dietary=None)
    assert quantities.recommend([dish], event, RULES)[dish.id] == 1


def test_recommendation_respects_minimum_and_weight_steps():
    minimum = _dish(dietary=VEGAN, min_quantity=Decimal(5))
    assert quantities.recommend([minimum], EVENT, RULES)[minimum.id] == 5
    weight = _dish(dietary=VEGAN, pricing_unit=PricingUnit.PER_WEIGHT, servings_per_unit=Decimal(8))
    assert quantities.recommend([weight], EVENT, RULES)[weight.id] == Decimal("3.0")  # 2.75.


def _kosher(value):
    return SimpleNamespace(dietary=SimpleNamespace(kashrut_class=value))


def test_kashrut_mixing_follows_the_caterer_rule():
    mixed = [_kosher(KashrutClass.MEAT), _kosher(KashrutClass.DAIRY)]
    assert kashrut.check_order(mixed, KashrutMixingRule.BLOCK).status == "blocked"
    assert kashrut.check_order(mixed, KashrutMixingRule.WARN).status == "warn"
    fine = [_kosher(KashrutClass.MEAT), _kosher(KashrutClass.PAREVE)]
    assert kashrut.check_order(fine, KashrutMixingRule.BLOCK).status == "ok"


def test_unknown_kashrut_is_reported():
    dishes = [_kosher(KashrutClass.MEAT), SimpleNamespace(dietary=None)]
    check = kashrut.check_order(dishes, KashrutMixingRule.BLOCK)
    assert (check.status, check.has_unknown) == ("ok", True)


# Public catalog


def test_public_catalog_hides_unavailable_dishes_and_inactive_categories(client, shop):
    hidden = shop.post("categories", {"name": "מוסתרת"})
    shop.dish("נסתרת", "1.00", "pareve", category=hidden)
    shop.patch(f"categories/{hidden['id']}", {"is_active": False})
    shop.patch(f"dishes/{shop.dairy['id']}", {"is_available": False})
    base = f"/api/c/{shop.tenant.slug}/catalog"

    assert [dish["name"] for dish in client.get(f"{base}/dishes").json()] == ["עוף"]
    assert "מוסתרת" not in [c["name"] for c in client.get(f"{base}/categories").json()]


def test_filters_never_treat_unknown_as_a_match(client, shop):
    body = {
        "category_id": shop.category["id"],
        "name": "לא ידוע",
        "pricing_unit": "per_item",
        "unit_price": "1",
    }
    shop.post("dishes", body)
    url = f"/api/c/{shop.tenant.slug}/catalog/dishes"
    assert client.get(url, params={"vegan": True}).json() == []
    assert client.get(url, params={"vegetarian": True}).json() == []
    assert [d["name"] for d in client.get(url, params={"kashrut": "meat"}).json()] == ["עוף"]


def test_availability_and_cities_are_public(client, shop):
    base = f"/api/c/{shop.tenant.slug}"
    shop.post("blocked-dates", {"date": "2031-02-02"})
    body = client.get(f"{base}/availability").json()
    assert "2031-02-02" in body["blocked_dates"]
    assert len(body["slots"]) == 2
    assert client.get(f"{base}/delivery-cities").json() == [{"city": "חיפה", "fee": "50.00"}]


# Private link


def test_create_returns_a_token_that_is_stored_only_hashed(session, shop):
    order = shop.order()
    stored = session.scalar(text("select access_token_hash from orders"))
    assert order.token != stored
    assert len(order.token) >= 43
    assert order.data["version"] == 1


def test_order_needs_its_own_token(client, shop):
    first, second = shop.order(), shop.order()
    assert client.get(first.url).status_code == 401
    assert client.get(first.url, headers={"X-Order-Token": "wrong"}).status_code == 404
    assert client.get(first.url, headers=second.headers).status_code == 404
    assert client.get(first.url, headers=first.headers).status_code == 200


def test_every_order_route_requires_the_token(client, shop):
    order = shop.order()
    routes = [
        (method, path)
        for path, operations in client.app.openapi()["paths"].items()
        if path.startswith("/api/orders")
        for method in operations
    ]
    assert len(routes) == 10
    for method, path in routes:
        url = path.replace("{order_id}", order.data["id"])
        url = url.replace("{dish_id}", str(uuid4())).replace("{proposal_id}", str(uuid4()))
        response = client.request(method.upper(), f"{url}?version=1", json={})
        assert response.status_code in (401, 422), f"{method} {path}"
        assert client.get(order.url, headers=order.headers).json()["version"] == 1


def test_order_response_never_contains_the_token_hash(client, shop):
    order = shop.order()
    assert "hash" not in client.get(order.url, headers=order.headers).text


@pytest.mark.parametrize(
    "event",
    [
        {"adults": 0, "children": 0},
        {"adults": 2, "children": 0, "vegetarian_guests": 2, "vegan_guests": 1},
        {"adults": -1},
    ],
)
def test_guest_counts_are_validated(shop, event):
    details = customer_details(shop.slot["id"])
    details["event"] |= {"vegetarian_guests": 0, "vegan_guests": 0} | event
    assert shop.create(details).status_code == 422


def test_special_diets_can_fill_the_whole_guest_count(shop):
    details = customer_details(shop.slot["id"])
    details["event"] |= {"adults": 5, "children": 0, "vegetarian_guests": 3, "vegan_guests": 2}
    assert shop.create(details).status_code == 201


@pytest.mark.parametrize(
    "extra", [{"caterer_id": str(uuid4())}, {"status": "approved"}, {"total": "1"}]
)
def test_body_cannot_set_protected_fields(shop, extra):
    assert shop.create(customer_details(shop.slot["id"]) | extra).status_code == 422


# Scheduling


def test_past_date_is_rejected(shop):
    details = customer_details(shop.slot["id"])
    details["event"]["event_date"] = (availability.today() - timedelta(days=1)).isoformat()
    assert shop.create(details).json()["error"]["code"] == "date_unavailable"


def test_blocked_date_is_rejected(shop):
    shop.post("blocked-dates", {"date": EVENT_DAY.isoformat()})
    details = customer_details(shop.slot["id"])
    assert shop.create(details).json()["error"]["code"] == "date_unavailable"


@pytest.mark.parametrize("problem", ["wrong_weekday", "wrong_type", "missing"])
def test_unusable_slot_is_rejected(shop, problem):
    details = customer_details(shop.slot["id"])
    if problem == "wrong_weekday":
        details["event"]["event_date"] = (EVENT_DAY + timedelta(days=1)).isoformat()
    elif problem == "wrong_type":
        details["time_slot_id"] = shop.delivery_slot["id"]
    else:
        details["time_slot_id"] = str(uuid4())
    assert shop.create(details).json()["error"]["code"] == "slot_unavailable"


def test_failed_order_leaves_nothing_behind(session, shop):
    details = customer_details(str(uuid4()))
    assert shop.create(details).status_code == 422
    session.rollback()
    assert session.scalar(text("select count(*) from customers")) == 0


def test_delivery_adds_the_zone_fee(shop):
    order = shop.order(
        fulfillment_type="delivery",
        time_slot_id=shop.delivery_slot["id"],
        delivery_city="חיפה",
        delivery_address="הרצל 1",
    )
    data = order.add(shop.meat)
    assert (data["subtotal"], data["delivery_fee"], data["total"]) == ("200.00", "50.00", "250.00")


def test_delivery_to_an_unserved_city_is_rejected(shop):
    details = customer_details(
        shop.delivery_slot["id"],
        fulfillment_type="delivery",
        delivery_city="אילת",
        delivery_address="א",
    )
    assert shop.create(details).json()["error"]["code"] == "delivery_unavailable"


def test_delivery_needs_an_address(shop):
    details = customer_details(
        shop.delivery_slot["id"], fulfillment_type="delivery", delivery_city="חיפה"
    )
    assert shop.create(details).status_code == 422


def test_city_cannot_belong_to_two_zones(client, shop):
    body = {"name": "צפון", "fee": "70", "cities": ["חיפה"]}
    response = client.post(f"{ADMIN}/delivery-zones", json=body, headers=shop.headers)
    assert response.status_code == 409


def test_used_slot_cannot_be_deleted(client, shop):
    shop.order()
    url = f"{ADMIN}/time-slots/{shop.slot['id']}"
    assert client.delete(url, headers=shop.headers).status_code == 409


# Items and versions


def test_recommendation_and_price_reach_the_customer(shop):
    line = shop.order().add(shop.meat)
    assert line["lines"][0]["line_total"] == "200.00"
    assert line["lines"][0]["recommended_quantity"] is not None


def test_stale_version_is_rejected(client, shop):
    order = shop.order()
    stale = order.data["version"]
    order.add(shop.meat)
    url = f"{order.url}/items/{shop.dairy['id']}"
    response = client.put(url, json={"quantity": "1", "version": stale}, headers=order.headers)
    assert order.error(response) == (409, "order_version_conflict")


def test_remove_item(client, shop):
    order = shop.order()
    order.add(shop.meat)
    url = f"{order.url}/items/{shop.meat['id']}?version={order.data['version']}"
    response = client.delete(url, headers=order.headers)
    assert response.json()["lines"] == []
    assert response.json()["total"] == "0.00"


def test_tray_quantity_must_be_whole(client, shop):
    order = shop.order()
    url = f"{order.url}/items/{shop.meat['id']}"
    body = {"quantity": "1.5", "version": order.data["version"]}
    assert client.put(url, json=body, headers=order.headers).status_code == 422


def test_unavailable_dish_cannot_be_added(client, shop):
    order = shop.order()
    shop.patch(f"dishes/{shop.meat['id']}", {"is_available": False})
    url = f"{order.url}/items/{shop.meat['id']}"
    body = {"quantity": "1", "version": order.data["version"]}
    response = client.put(url, json=body, headers=order.headers)
    assert order.error(response) == (409, "dish_unavailable")


def test_update_details(client, shop):
    order = shop.order()
    body = customer_details(shop.slot["id"]) | {"version": order.data["version"]}
    body["customer"]["full_name"] = "שם חדש"
    response = client.patch(order.url, json=body, headers=order.headers)
    assert response.json()["customer"]["full_name"] == "שם חדש"
    assert response.json()["version"] == 2


# Submission


def test_submit_freezes_prices(client, shop):
    order = shop.order()
    order.add(shop.meat)
    assert order.submit().json()["status"] == "pending_approval"

    shop.patch(f"dishes/{shop.meat['id']}", {"unit_price": "999.00", "name": "שם אחר"})
    frozen = client.get(order.url, headers=order.headers).json()
    assert frozen["total"] == "200.00"
    assert frozen["lines"][0]["name"] == "עוף"


def test_draft_follows_live_prices(client, shop):
    order = shop.order()
    order.add(shop.meat)
    shop.patch(f"dishes/{shop.meat['id']}", {"unit_price": "1.00"})
    assert client.get(order.url, headers=order.headers).json()["total"] == "2.00"


def test_empty_order_cannot_be_submitted(shop):
    order = shop.order()
    assert order.error(order.submit()) == (422, "empty_order")


def test_submitted_order_cannot_be_changed_or_resubmitted(client, shop):
    order = shop.order()
    order.add(shop.meat)
    order.store(order.submit())

    url = f"{order.url}/items/{shop.dairy['id']}"
    body = {"quantity": "1", "version": order.data["version"]}
    assert order.error(client.put(url, json=body, headers=order.headers))[1] == "invalid_transition"
    assert order.error(order.submit())[1] == "invalid_transition"


def test_mixing_blocked(shop):
    shop.patch("profile", {"kashrut_mixing_rule": "block"})
    order = shop.order()
    order.add(shop.meat)
    assert order.add(shop.dairy)["kashrut"]["status"] == "blocked"
    assert order.error(order.submit()) == (409, "kashrut_mixing_blocked")
    acknowledged = order.submit(acknowledge_kashrut_warning=True)
    assert order.error(acknowledged)[1] == "kashrut_mixing_blocked"


def test_mixing_warning_needs_acknowledgement(shop):
    order = shop.order()
    order.add(shop.meat)
    order.add(shop.dairy)
    assert order.error(order.submit()) == (409, "kashrut_warning_not_acknowledged")
    assert order.submit(acknowledge_kashrut_warning=True).status_code == 200


def test_minimum_quantity_is_enforced_at_submit(shop):
    shop.patch(f"dishes/{shop.meat['id']}", {"min_quantity": "3"})
    order = shop.order()
    order.add(shop.meat)
    assert order.error(order.submit()) == (422, "below_minimum")


def test_dish_withdrawn_after_adding_blocks_submit(shop):
    order = shop.order()
    order.add(shop.meat)
    shop.patch(f"dishes/{shop.meat['id']}", {"is_available": False})
    assert order.error(order.submit()) == (409, "dish_unavailable")


def test_date_blocked_after_drafting_blocks_submit(shop):
    order = shop.order()
    order.add(shop.meat)
    shop.post("blocked-dates", {"date": EVENT_DAY.isoformat()})
    assert order.error(order.submit())[1] == "date_unavailable"


def test_full_slot_rejects_the_next_submission(shop):
    shop.patch(f"time-slots/{shop.slot['id']}", {"capacity": 1})
    first, second = shop.order(), shop.order()
    first.add(shop.meat)
    second.add(shop.meat)
    assert first.submit().status_code == 200
    assert second.error(second.submit()) == (409, "slot_full")


# Isolation


def test_order_cannot_use_another_caterers_dish_or_slot(client, make_tenant):
    a = Shop(client, make_tenant("caterer-a"))
    b = Shop(client, make_tenant("caterer-b"))
    order = a.order()

    url = f"{order.url}/items/{b.meat['id']}"
    body = {"quantity": "1", "version": order.data["version"]}
    assert client.put(url, json=body, headers=order.headers).status_code == 404
    assert a.create(customer_details(b.slot["id"])).json()["error"]["code"] == "slot_unavailable"


def test_catalog_shows_only_the_slugs_caterer(client, make_tenant):
    a = Shop(client, make_tenant("caterer-a"))
    b = Shop(client, make_tenant("caterer-b"))
    b.patch(f"dishes/{b.meat['id']}", {"name": "של ב"})
    names = [d["name"] for d in client.get(f"/api/c/{a.tenant.slug}/catalog/dishes").json()]
    assert "של ב" not in names


def test_a_caterer_login_gives_no_order_access(client, shop):
    order = shop.order()
    assert client.get(order.url, headers=shop.headers).status_code == 401


def test_inactive_caterer_cannot_take_orders(session, shop):
    order = shop.order()
    order.add(shop.meat)
    session.execute(text("update caterers set is_active = false"))
    session.commit()

    assert shop.create(customer_details(shop.slot["id"])).status_code == 404
    assert order.submit().status_code == 404


def test_customer_page_is_served_for_any_slug(client):
    response = client.get("/c/some-caterer/")
    assert response.status_code == 200
    assert 'dir="rtl"' in response.text
