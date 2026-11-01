"""Walks a customer through ordering in a real browser. Tests run in order on one session."""

import json
import os
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from conftest import SHOTS, call

EVENT_DAY = "2031-01-07"  # A Tuesday.
TUESDAY = 2
PHOTO = Path(os.environ.get("E2E_DISH_PHOTO", Path(__file__).parent / "fixtures" / "dish.png"))


@pytest.fixture(scope="module", autouse=True)
def seeded_menu(base_url):
    token = call(base_url, "/auth/v1/token", {"password": "right"})["access_token"]

    def admin(path, body, method="POST"):
        return call(base_url, f"/api/admin{path}", body, token, method)

    mains = admin("/categories", {"name": "עיקריות", "category_type": "main"})
    salads = admin("/categories", {"name": "סלטים", "category_type": "salad"})

    def dish(name, price, category, dietary, **fields):
        body = {
            "category_id": category["id"],
            "name": name,
            "pricing_unit": "per_tray",
            "unit_price": price,
        }
        created = admin("/dishes", body | fields)
        admin(f"/dishes/{created['id']}/dietary", dietary, "PUT")
        return created

    gluten = admin_allergen(base_url)
    dish("עוף בתנור", "200.00", mains, {"kashrut_class": "meat"}, servings_per_unit="10")
    lasagna = dish(
        "לזניה",
        "150.00",
        mains,
        {
            "kashrut_class": "dairy",
            "is_vegetarian": True,
            "allergens": [{"allergen_id": gluten, "status": "contains"}],
        },
        calories_per_portion=450,
    )
    upload_photo(base_url, token, lasagna["id"])
    dish(
        "טבולה",
        "90.00",
        salads,
        {"kashrut_class": "pareve", "is_vegetarian": True, "is_vegan": True},
        servings_per_unit="12",
    )
    slot = {"weekday": TUESDAY, "start_time": "09:00", "end_time": "12:00"}
    admin("/time-slots", slot | {"fulfillment_type": "pickup"})
    admin("/time-slots", slot | {"fulfillment_type": "delivery"})
    admin("/delivery-zones", {"name": "מרכז", "fee": "50.00", "cities": ["חיפה"]})
    admin("/profile", {"kashrut_status": "כשר בהשגחת הרבנות", "brand_color": "#1f5f8b"}, "PATCH")
    return admin


def upload_photo(base_url, token, dish_id):
    boundary = "e2e-boundary"
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="dish"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + PHOTO.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(  # noqa: S310
        f"{base_url}/api/admin/dishes/{dish_id}/image",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    urllib.request.urlopen(request).close()  # noqa: S310


def admin_allergen(base_url):
    with urllib.request.urlopen(f"{base_url}/api/allergens") as response:  # noqa: S310
        return next(a["id"] for a in json.loads(response.read()) if a["name"] == "גלוטן")


def fill(page: Page, label: str, value: str) -> None:
    page.get_by_label(label, exact=True).fill(value)


def card(page: Page, name: str):
    return page.locator("article.dish", has_text=name)


def total(page: Page):
    return page.locator(".total-bar strong")


def test_unknown_caterer_shows_a_hebrew_message(page: Page):
    page.goto("/c/no-such-caterer/")
    expect(page.get_by_role("heading", name="העמוד אינו זמין")).to_be_visible()
    expect(page.get_by_alt_text("Yummai")).to_be_visible()


def test_caterer_page_shows_branding_in_rtl(page: Page):
    page.goto("/c/taamim/")
    expect(page.get_by_role("heading", name="טעמים קייטרינג")).to_be_visible()
    expect(page.get_by_text("כשר בהשגחת הרבנות")).to_be_visible()
    expect(page.get_by_alt_text("Yummai")).to_be_visible()
    assert page.locator("html").get_attribute("dir") == "rtl"
    accent = page.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--color-accent')"
    )
    assert accent.strip() == "#1f5f8b"


def test_too_many_special_diets_are_rejected(page: Page):
    fill(page, "שם מלא", "דנה לוי")
    fill(page, "טלפון", "050-1234567")
    fill(page, "מבוגרים", "2")
    fill(page, "צמחונים", "5")
    fill(page, "תאריך", EVENT_DAY)
    page.get_by_label("שעה", exact=True).select_option(label="09:00–12:00")
    page.get_by_role("button", name="המשך לתפריט").click()
    expect(page.locator("#notice")).to_contain_text("נספרים מתוך מספר הסועדים")
    expect(page.get_by_role("button", name="המשך לתפריט")).to_be_visible()


def test_event_details_lead_to_the_menu(page: Page):
    fill(page, "מבוגרים", "20")
    fill(page, "ילדים", "4")
    fill(page, "צמחונים", "2")
    page.get_by_role("button", name="המשך לתפריט").click()
    expect(card(page, "עוף בתנור")).to_be_visible()
    assert "#order=" in page.url


def test_dish_card_shows_dietary_truthfully(page: Page):
    lasagna = card(page, "לזניה")
    expect(lasagna).to_contain_text("כשרות: חלבי")
    expect(lasagna).to_contain_text("קלוריות: 450")
    expect(card(page, "עוף בתנור")).to_contain_text("קלוריות: לא צוין")

    lasagna.get_by_text("מידע על אלרגנים").click()
    sheet = page.locator("dialog.dish-sheet")
    expect(sheet).to_contain_text("מכיל: גלוטן")
    expect(sheet).to_contain_text("לא ידוע (לא אומת): חלב")
    expect(sheet).to_contain_text("מידע שלא אומת אינו אומר שהמנה בטוחה")
    assert sheet.locator("img").evaluate("img => img.naturalWidth") > 0
    page.screenshot(path=SHOTS / "customer-sheet.png")
    sheet.get_by_role("button", name="סגירה").click()
    expect(sheet).to_have_count(0)


def test_dish_without_a_photo_still_looks_finished(page: Page):
    expect(card(page, "עוף בתנור").locator(".dish-media")).to_have_text("ע")
    expect(page.locator(".category-title", has_text="עיקריות")).to_contain_text("2 מנות")
    assert card(page, "לזניה").locator("img").evaluate("img => img.naturalWidth") > 0


def test_adding_from_the_sheet_updates_the_sheet_and_the_page(page: Page):
    card(page, "טבולה").locator(".dish-open").click()
    sheet = page.locator("dialog.dish-sheet")
    sheet.get_by_role("button", name="הוספת טבולה").click()
    expect(sheet.get_by_role("button", name="עוד טבולה")).to_be_focused()
    sheet.get_by_role("button", name="פחות טבולה").click()
    expect(sheet.get_by_role("button", name="הוספת טבולה")).to_be_visible()
    sheet.get_by_role("button", name="סגירה").click()
    expect(total(page)).to_have_text("₪0.00")
    expect(page.locator("#notice")).to_have_count(1)


def test_filter_shows_only_confirmed_dishes(page: Page):
    page.get_by_label("טבעוני", exact=True).check()
    expect(card(page, "טבולה")).to_be_visible()
    expect(card(page, "לזניה")).to_have_count(0)
    page.get_by_label("טבעוני", exact=True).uncheck()


def test_adding_dishes_updates_total_and_recommends_quantity(page: Page):
    page.screenshot(path=SHOTS / "customer-menu.png")
    page.get_by_role("button", name="הוספת עוף בתנור").click()
    expect(total(page)).to_have_text("₪200.00")
    expect(card(page, "עוף בתנור")).to_contain_text("מומלץ: 3")
    page.get_by_role("button", name="עוד עוף בתנור").click()
    expect(total(page)).to_have_text("₪400.00")


def test_private_link_restores_the_order_after_reload(page: Page):
    page.reload()
    expect(total(page)).to_have_text("₪400.00")


def test_mixing_warning_must_be_acknowledged(page: Page):
    page.get_by_role("button", name="הוספת לזניה").click()
    expect(total(page)).to_have_text("₪550.00")
    page.get_by_role("button", name="לסיכום").click()
    expect(page.get_by_text("ההזמנה כוללת מנות בשריות וחלביות יחד")).to_be_visible()
    expect(page.locator("#app")).not_to_contain_text("null")
    page.screenshot(path=SHOTS / "customer-summary.png", full_page=True)

    page.get_by_role("button", name="שליחת בקשה להצעת מחיר").click()
    expect(page.locator("#notice")).to_have_class("notice error")
    expect(page.get_by_role("button", name="שליחת בקשה להצעת מחיר")).to_be_visible()


def test_blocked_mixing_stops_the_order(page: Page, seeded_menu):
    seeded_menu("/profile", {"kashrut_mixing_rule": "block"}, "PATCH")
    page.reload()
    page.get_by_role("button", name="לסיכום").click()
    expect(page.get_by_role("alert")).to_contain_text("הסירו אחת מהן")
    expect(page.get_by_role("button", name="שליחת בקשה להצעת מחיר")).to_be_disabled()

    page.get_by_role("button", name="חזרה לתפריט").click()
    page.get_by_role("button", name="פחות לזניה").click()
    expect(total(page)).to_have_text("₪400.00")


def test_submitting_shows_pending_not_confirmed(page: Page):
    page.get_by_role("button", name="לסיכום").click()
    page.get_by_role("button", name="שליחת בקשה להצעת מחיר").click()
    expect(page.locator(".status")).to_have_text("ממתין לאישור הקייטרינג")
    expect(page.get_by_alt_text("Yummai")).to_be_visible()
    expect(page.get_by_text("₪400.00").first).to_be_visible()
    page.screenshot(path=SHOTS / "customer-status.png", full_page=True)


def test_submitted_order_reopens_as_status_with_frozen_price(page: Page, seeded_menu):
    url = page.url
    page.goto("about:blank")
    page.goto(url)
    expect(page.locator(".status")).to_have_text("ממתין לאישור הקייטרינג")
    expect(page.get_by_role("button", name="הוספת עוף בתנור")).to_have_count(0)


def test_private_link_can_be_copied(page: Page):
    page.get_by_role("button", name="העתקת הקישור").click()
    expect(page.locator("#notice")).to_have_text("הקישור הועתק")
    assert "#order=" in page.evaluate("navigator.clipboard.readText()")


def test_a_broken_private_link_starts_cleanly(page: Page):
    page.goto("about:blank")
    page.goto("/c/taamim/#order=00000000-0000-0000-0000-000000000000.wrong")
    expect(page.locator("#notice")).to_have_text("הקישור להזמנה אינו תקין")
    expect(page.get_by_label("שם מלא", exact=True)).to_be_visible()


def test_delivery_order_includes_the_fee(page: Page):
    page.goto("about:blank")
    page.goto("/c/taamim/")
    fill(page, "שם מלא", "יוסי כהן")
    fill(page, "טלפון", "052-7654321")
    fill(page, "מבוגרים", "10")
    page.get_by_label("איסוף או משלוח", exact=True).select_option("delivery")
    fill(page, "תאריך", EVENT_DAY)
    page.get_by_label("שעה", exact=True).select_option(label="09:00–12:00")
    page.get_by_label("עיר", exact=True).select_option("חיפה")
    fill(page, "כתובת", "הרצל 1")
    page.get_by_role("button", name="המשך לתפריט").click()
    page.get_by_role("button", name="הוספת טבולה").click()
    expect(total(page)).to_have_text("₪140.00")


def test_no_sideways_scroll_and_no_javascript_errors(page: Page):
    sizes = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    assert sizes[0] <= sizes[1]
    assert page.errors == []


def test_computers_show_three_columns_and_the_live_order(page: Page):
    page.set_viewport_size({"width": 1366, "height": 800})
    panel = page.locator(".order-panel")
    expect(panel.locator(".order-line")).to_contain_text("טבולה")
    expect(panel.get_by_role("button", name="שינוי פרטי האירוע")).to_be_visible()
    expect(page.get_by_role("navigation", name="קטגוריות")).to_be_visible()
    url = page.url
    page.get_by_role("navigation", name="קטגוריות").get_by_role("button", name="סלטים").click()
    assert page.url == url
    panel.get_by_role("button", name="עוד טבולה").click()
    expect(panel.locator(".sum.total")).to_contain_text("₪230.00")
    expect(panel.get_by_role("button", name="עוד טבולה")).to_be_focused()
    panel.get_by_role("button", name="פחות טבולה").click()
    expect(panel.locator(".sum.total")).to_contain_text("₪140.00")
    expect(panel.get_by_role("button", name="פחות טבולה")).to_be_focused()
    panel.get_by_role("button", name="עוד טבולה").click()
    page.set_viewport_size({"width": 1366, "height": 400})
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    assert page.evaluate("window.scrollY") > 0
    assert abs(panel.evaluate("element => element.getBoundingClientRect().top") - 24) < 1
    page.set_viewport_size({"width": 1366, "height": 800})
    panel.get_by_role("button", name="הסרת טבולה").click()
    expect(panel.locator(".sum.total")).to_contain_text("₪50.00")
    panel.page.get_by_role("button", name="הוספת טבולה").click()
    sizes = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    assert sizes[0] <= sizes[1]
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=SHOTS / "customer-desktop.png")


def test_phone_opens_the_order_from_the_bottom_bar(page: Page):
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="ההזמנה שלי (1)").click()
    expect(page.locator(".order-panel")).to_contain_text("טבולה")
    page.screenshot(path=SHOTS / "customer-order-phone.png")
    page.locator(".order-panel").get_by_role("button", name="סגירה").click()
    expect(page.locator(".order-panel")).to_be_hidden()


def test_a_dish_taken_off_the_menu_can_still_be_removed(page: Page, seeded_menu, base_url):
    with urllib.request.urlopen(f"{base_url}/api/c/taamim/catalog/dishes") as response:  # noqa: S310
        dish = next(d for d in json.loads(response.read()) if d["name"] == "טבולה")
    seeded_menu(f"/dishes/{dish['id']}", {"is_available": False}, "PATCH")
    page.reload()
    page.get_by_role("button", name="ההזמנה שלי (1)").click()
    page.locator(".order-panel").get_by_role("button", name="הסרת טבולה").click()
    expect(total(page)).to_have_text("₪50.00")
    expect(page.locator(".order-panel .order-line")).to_have_count(0)
    page.locator(".order-panel").get_by_role("button", name="סגירה").click()
    seeded_menu(f"/dishes/{dish['id']}", {"is_available": True}, "PATCH")


def test_step_buttons_save_edits_to_the_details(page: Page):
    page.reload()
    page.get_by_role("button", name="פרטי האירוע").click()
    fill(page, "שם מלא", "יוסי לוי")
    page.get_by_role("button", name="סיכום").click()
    expect(page.get_by_role("heading", name="סיכום ההזמנה")).to_be_visible()
    expect(page.locator(".panel-person").first).to_contain_text("יוסי לוי")


def test_side_column_welcomes_with_the_caterer_initial(page: Page):
    page.goto("about:blank")
    page.goto("/c/taamim/")
    expect(page.locator(".side h1")).to_have_text("ברוכים הבאים לטעמים קייטרינג")
    expect(page.locator(".logo")).to_have_text("ט")
    page.screenshot(path=SHOTS / "customer-welcome.png")


def test_screenshots_were_written():
    assert Path(SHOTS / "customer-status.png").exists()
