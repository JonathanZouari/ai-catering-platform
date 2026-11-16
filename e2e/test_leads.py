"""The lead CRM in a real browser: a submitted request shows up scored, and the caterer works it."""

import pytest
from playwright.sync_api import Page, expect
from test_accessibility import assert_no_axe_violations
from test_approval import place_order

from conftest import SHOTS, call


@pytest.fixture(scope="module", autouse=True)
def lead(base_url):
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
    place_order(base_url, slot["id"], dish["id"], "רונית שדה")


def test_lead_appears_scored_with_a_text_label(page: Page):
    page.goto("/admin/")
    page.get_by_label("אימייל", exact=True).fill("owner@example.com")
    page.get_by_label("סיסמה", exact=True).fill("right")
    page.get_by_role("button", name="כניסה").click()
    page.get_by_role("link", name="לידים", exact=True).click()
    row = page.locator(".order-cards li", has_text="רונית שדה")
    expect(row).to_contain_text("סיכוי")
    expect(row).to_contain_text("%")
    expect(row).to_contain_text("חדש")
    page.screenshot(path=SHOTS / "leads-list.png", full_page=True)
    assert_no_axe_violations(page, "the leads list")


def test_detail_explains_the_score_and_lists_unknowns(page: Page):
    page.get_by_role("button", name="פתיחת הליד של רונית שדה").click()
    expect(page.get_by_role("heading", name="למה הציון הזה")).to_be_visible()
    expect(page.locator("main")).to_contain_text("לא ידוע, ולא נספר לרעה")
    page.screenshot(path=SHOTS / "lead-detail.png", full_page=True)
    assert_no_axe_violations(page, "the lead detail")


def test_caterer_changes_the_stage_and_adds_a_note(page: Page):
    page.get_by_label("שלב").select_option("won")
    expect(page.locator("main")).to_contain_text("השלב שונה לנסגר")
    page.get_by_role("button", name="הוספת הערה").click()
    page.get_by_label("הערה", exact=True).fill("דיברנו בטלפון, מחכה לאישור סופי")
    page.get_by_role("button", name="שמירה").click()
    expect(page.locator("main")).to_contain_text("דיברנו בטלפון")


def test_stage_filter_and_no_javascript_errors(page: Page):
    page.get_by_role("button", name="חזרה לרשימה").click()
    page.get_by_label("הצגת לידים").select_option("new")
    expect(page.get_by_text("אין לידים להצגה.")).to_be_visible()
    page.get_by_label("הצגת לידים").select_option("won")
    expect(page.locator(".order-cards li", has_text="רונית שדה")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not page.errors
