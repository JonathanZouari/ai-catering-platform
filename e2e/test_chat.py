"""The AI chat in a real browser, with a scripted model. Tests run in order on one session."""

import pytest
from playwright.sync_api import Page, expect

from conftest import SHOTS, call

XSS = "<img src=x onerror=window.pwned=1>"


@pytest.fixture(scope="module", autouse=True)
def seeded_menu(base_url):
    token = call(base_url, "/auth/v1/token", {"password": "right"})["access_token"]

    def admin(path, body, method="POST"):
        return call(base_url, f"/api/admin{path}", body, token, method)

    category = admin("/categories", {"name": "סלטים", "category_type": "salad"})
    dish = admin(
        "/dishes",
        {
            "category_id": category["id"],
            "name": "טבולה",
            "pricing_unit": "per_tray",
            "unit_price": "90.00",
        },
    )
    admin(f"/dishes/{dish['id']}/dietary", {"kashrut_class": "pareve"}, "PUT")
    slot = {"fulfillment_type": "pickup", "weekday": 2, "start_time": "09:00", "end_time": "12:00"}
    admin("/time-slots", slot)


def total(page: Page):
    return page.locator(".total-bar strong")


def ask(page: Page, text: str) -> None:
    page.get_by_label("הודעה לעוזר").fill(text)
    page.get_by_role("button", name="שליחה").click()


def test_customer_opens_the_chat_from_the_menu(page: Page):
    page.goto("/c/taamim/")
    page.get_by_label("שם מלא", exact=True).fill("דנה לוי")
    page.get_by_label("טלפון", exact=True).fill("050-1234567")
    page.get_by_label("מבוגרים", exact=True).fill("10")
    page.get_by_label("תאריך", exact=True).fill("2031-01-07")
    page.get_by_label("שעה", exact=True).select_option(label="09:00–12:00")
    expect(page.get_by_role("button", name="שאלו את העוזר")).to_be_hidden()
    page.get_by_role("button", name="המשך לתפריט").click()

    page.get_by_role("button", name="שאלו את העוזר").click()
    expect(page.get_by_text("העוזר מציע, ואתם מאשרים")).to_be_visible()


def test_reply_is_shown_as_text(page: Page):
    ask(page, XSS)
    expect(page.locator(".bubble.assistant").last).to_contain_text(XSS)
    assert page.evaluate("window.pwned") is None


def test_proposal_changes_nothing_until_approved(page: Page):
    ask(page, "הוסיפו טבולה")
    card = page.locator(".proposal")
    expect(card).to_contain_text("הוספה: טבולה × 2")
    expect(card).to_contain_text("₪180.00")
    page.screenshot(path=SHOTS / "chat-proposal.png")
    expect(total(page)).to_have_text("₪0.00")

    card.get_by_role("button", name="אישור השינוי").click()
    expect(card).to_have_count(0)
    expect(total(page)).to_have_text("₪180.00")


def test_rejecting_keeps_the_order(page: Page):
    ask(page, "הוסיפו טבולה")
    card = page.locator(".proposal")
    card.get_by_role("button", name="דחייה").click()
    expect(card).to_have_count(0)
    expect(total(page)).to_have_text("₪180.00")


def test_pending_card_survives_reload(page: Page):
    ask(page, "הוסיפו טבולה")
    expect(page.locator(".proposal")).to_be_visible()
    page.reload()
    page.get_by_role("button", name="שאלו את העוזר").click()
    expect(page.locator(".proposal")).to_be_visible()
    expect(page.locator(".bubble.user").first).to_be_visible()


def test_stale_card_is_refused(page: Page):
    page.get_by_role("button", name="סגירה").click()
    page.get_by_role("button", name="עוד טבולה").click()
    expect(total(page)).to_have_text("₪90.00".replace("90", "270"))

    page.get_by_role("button", name="שאלו את העוזר").click()
    page.locator(".proposal").get_by_role("button", name="אישור השינוי").click()
    expect(page.locator("#notice")).to_have_text("ההזמנה השתנתה. בקשו הצעה חדשה")
    expect(page.locator(".proposal")).to_have_count(0)
    expect(total(page)).to_have_text("₪270.00")


def test_no_sideways_scroll_and_rtl(page: Page):
    sizes = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    assert sizes[0] <= sizes[1]
    assert page.locator("html").get_attribute("dir") == "rtl"
    page.screenshot(path=SHOTS / "chat-open.png")


def test_limit_turns_chat_off_and_ordering_continues(page: Page):
    for _ in range(10):
        ask(page, "עוד שאלה")
        if page.get_by_text("העוזר אינו זמין כרגע. אפשר להמשיך להזמין בתפריט").is_visible():
            break
        page.wait_for_timeout(300)
        if page.get_by_label("הודעה לעוזר").is_disabled():
            break
    expect(page.get_by_text("העוזר אינו זמין כרגע. אפשר להמשיך להזמין בתפריט")).to_be_visible()

    page.get_by_role("button", name="סגירה").click()
    page.get_by_role("button", name="עוד טבולה").click()
    expect(total(page)).to_have_text("₪360.00")


def test_chat_is_gone_after_submission(page: Page):
    page.get_by_role("button", name="לסיכום").click()
    page.get_by_role("button", name="שליחת בקשה להצעת מחיר").click()
    expect(page.locator(".status")).to_be_visible()
    expect(page.get_by_role("button", name="שאלו את העוזר")).to_be_hidden()


def test_no_javascript_errors(page: Page):
    assert page.errors == []
