"""A caterer answers quote requests in a real browser, and the customer sees the answer."""

import pytest
from playwright.sync_api import Page, expect

from conftest import SHOTS, call

EVENT_DAY = "2031-01-07"  # A Tuesday.
XSS = "<img src=x onerror=window.pwned=1>"


def place_order(base_url, slot_id, dish_id, name, notes=None):
    details = {
        "customer": {"full_name": name, "phone": "050-1234567"},
        "event": {
            "event_type": "יום הולדת",
            "event_date": EVENT_DAY,
            "adults": 20,
            "children": 4,
            "vegetarian_guests": 2,
            "dietary_notes": notes,
        },
        "fulfillment_type": "pickup",
        "time_slot_id": slot_id,
    }
    created = call(base_url, "/api/c/taamim/orders", details)
    order, token = created["order"], created["token"]
    headers = {"X-Order-Token": token}
    url = f"/api/orders/{order['id']}"
    body = {"quantity": "2", "version": order["version"]}
    order = call(base_url, f"{url}/items/{dish_id}", body, method="PUT", headers=headers)
    call(base_url, f"{url}/submit", {"version": order["version"]}, headers=headers)
    return f"/c/taamim/#order={order['id']}.{token}"


@pytest.fixture(scope="module", autouse=True)
def links(base_url):
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
    admin("/profile", {"contact_phone": "03-1234567"}, "PATCH")
    return {
        name: place_order(base_url, slot["id"], dish["id"], name, notes)
        for name, notes in [("דנה לוי", XSS), ("יוסי כהן", None)]
    }


def open_order(page: Page, name: str) -> None:
    page.get_by_role("button", name=f"פתיחת ההזמנה של {name}").click()
    expect(page.get_by_role("heading", name=f"הזמנה של {name}")).to_be_visible()


def see_customer_page(page: Page, link: str) -> None:
    page.goto("about:blank")
    page.goto(link)


def back_to_dashboard(page: Page) -> None:
    page.goto("/admin/")
    expect(page.get_by_role("heading", name="הזמנות")).to_be_visible()


def test_customer_waits_for_the_caterer(page: Page, links):
    see_customer_page(page, links["דנה לוי"])
    expect(page.locator(".status")).to_have_text("ממתין לאישור הקייטרינג")


def test_caterer_lands_on_waiting_orders_after_login(page: Page):
    page.goto("/admin/")
    page.get_by_label("אימייל", exact=True).fill("owner@example.com")
    page.get_by_label("סיסמה", exact=True).fill("right")
    page.get_by_role("button", name="כניסה").click()
    row = page.locator(".rows li", has_text="דנה לוי")
    expect(row).to_contain_text("24 סועדים")
    expect(row).to_contain_text("₪400.00")
    expect(page.locator(".rows li", has_text="יוסי כהן")).to_be_visible()
    page.screenshot(path=SHOTS / "orders-list.png", full_page=True)


def test_detail_shows_customer_text_without_running_it(page: Page):
    open_order(page, "דנה לוי")
    expect(page.get_by_text(XSS)).to_be_visible()
    assert page.evaluate("window.pwned") is None
    link = page.get_by_role("link", name="050-1234567")
    assert link.get_attribute("href") == "tel:050-1234567"
    expect(page.get_by_text("2 צמחונים")).to_be_visible()
    expect(page.locator("#view")).not_to_contain_text("null")
    page.screenshot(path=SHOTS / "order-detail.png", full_page=True)


def test_approval_moves_the_order_out_of_waiting(page: Page):
    page.get_by_role("button", name="אישור ההזמנה").click()
    page.get_by_label("הערה ללקוח", exact=True).fill("נתראה באירוע")
    page.locator("dialog button[type=submit]").click()
    expect(page.locator("#view .badge").first).to_have_text("אושר")
    expect(page.get_by_role("button", name="דחיית ההזמנה")).to_have_count(0)

    page.get_by_role("button", name="חזרה לרשימה").click()
    expect(page.locator(".rows li", has_text="דנה לוי")).to_have_count(0)


def test_customer_sees_approval_with_note_and_contact(page: Page, links):
    see_customer_page(page, links["דנה לוי"])
    expect(page.locator(".status")).to_have_text("ההזמנה אושרה")
    expect(page.get_by_text("נתראה באירוע")).to_be_visible()
    expect(page.get_by_text("התשלום מתואם ישירות מול העסק")).to_be_visible()
    expect(page.get_by_role("link", name="03-1234567")).to_be_visible()
    expect(page.get_by_role("button", name="הוספת עוף בתנור")).to_have_count(0)
    page.screenshot(path=SHOTS / "customer-approved.png", full_page=True)


def test_rejection_needs_a_note(page: Page):
    back_to_dashboard(page)
    open_order(page, "יוסי כהן")
    page.get_by_role("button", name="דחיית ההזמנה").click()
    page.locator("dialog button[type=submit]").click()
    expect(page.locator("dialog")).to_be_visible()

    page.get_by_label("הערה ללקוח", exact=True).fill("התאריך תפוס")
    page.locator("dialog button[type=submit]").click()
    expect(page.locator("#view .badge").first).to_have_text("נדחה")


def test_customer_refreshes_to_see_the_answer(page: Page, links):
    see_customer_page(page, links["יוסי כהן"])
    expect(page.locator(".status")).to_have_text("ההזמנה נדחתה")
    expect(page.get_by_text("התאריך תפוס")).to_be_visible()
    page.get_by_role("button", name="בדיקת עדכון").click()
    expect(page.locator(".status")).to_have_text("ההזמנה נדחתה")


def test_decided_orders_stay_readable_and_final(page: Page):
    back_to_dashboard(page)
    page.get_by_label("סינון", exact=True).select_option("")
    open_order(page, "יוסי כהן")
    expect(page.get_by_text("התאריך תפוס")).to_be_visible()
    expect(page.get_by_role("button", name="אישור ההזמנה")).to_have_count(0)


def test_no_sideways_scroll_and_no_javascript_errors(page: Page):
    sizes = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    assert sizes[0] <= sizes[1]
    assert page.locator("html").get_attribute("dir") == "rtl"
    assert page.errors == []
