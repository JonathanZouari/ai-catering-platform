"""The caterer sets an alert address in the dashboard and hears about a real order."""

import json
import urllib.request

from playwright.sync_api import Page, expect

from conftest import call
from test_approval import place_order

ADDRESS = "owner@example.com"
FIELD = "אימייל להתראות על הזמנות חדשות"


def outbox(base_url):
    with urllib.request.urlopen(f"{base_url}/test-only/sent-emails") as response:  # noqa: S310
        return json.loads(response.read())


def seed_menu(base_url):
    token = call(base_url, "/auth/v1/token", {"password": "right"})["access_token"]

    def admin(path, body, method="POST"):
        return call(base_url, f"/api/admin{path}", body, token, method)

    category = admin("/categories", {"name": "עיקריות", "category_type": "main"})
    dish = admin(
        "/dishes",
        {
            "category_id": category["id"],
            "name": "עוף בתנור",
            "pricing_unit": "per_tray",
            "unit_price": "200.00",
        },
    )
    admin(f"/dishes/{dish['id']}/dietary", {"kashrut_class": "meat"}, "PUT")
    slot = admin(
        "/time-slots",
        {"fulfillment_type": "pickup", "weekday": 2, "start_time": "09:00", "end_time": "12:00"},
    )
    return slot["id"], dish["id"]


def test_saved_address_receives_a_new_order_email(page: Page, base_url):
    page.goto("/admin/")
    page.get_by_label("אימייל", exact=True).fill(ADDRESS)
    page.get_by_label("סיסמה", exact=True).fill("right")
    page.get_by_role("button", name="כניסה").click()
    page.get_by_role("link", name="פרופיל העסק").click()
    page.get_by_label(FIELD).fill(ADDRESS)
    page.get_by_role("button", name="שמירה").click()
    expect(page.locator("#notice")).to_have_text("הפרטים נשמרו")
    page.reload()
    expect(page.get_by_label(FIELD)).to_have_value(ADDRESS)

    slot_id, dish_id = seed_menu(base_url)
    place_order(base_url, slot_id, dish_id, "דנה לוי")

    [email] = outbox(base_url)
    assert email["to"] == ADDRESS
    assert "מספר סועדים: 24" in email["text"]
    assert "דנה לוי" not in email["text"]
    assert page.errors == []
