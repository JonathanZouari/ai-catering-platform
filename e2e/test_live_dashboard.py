"""The caterer's order list updates by itself when Realtime reports a change."""

import time

import pytest
from playwright.sync_api import Page, expect

from conftest import SHOTS, call
from test_approval import place_order


@pytest.fixture(scope="module", autouse=True)
def menu(base_url):
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
    slot = admin(
        "/time-slots",
        {"fulfillment_type": "pickup", "weekday": 2, "start_time": "09:00", "end_time": "12:00"},
    )
    return {"dish": dish["id"], "slot": slot["id"]}


def log_in(page: Page) -> None:
    page.goto("/admin/")
    page.get_by_label("אימייל", exact=True).fill("owner@example.com")
    page.get_by_label("סיסמה", exact=True).fill("right")
    page.get_by_role("button", name="כניסה").click()
    expect(page.get_by_text("אין הזמנות להצגה")).to_be_visible()


def realtime_change(base_url: str, joined: int = 1) -> None:
    """Waits until the dashboard has joined the channel, then reports a changed order."""
    for _ in range(50):
        if call(base_url, "/test-only/realtime-change", {})["sockets"] >= joined:
            return
        time.sleep(0.1)
    pytest.fail("the dashboard never joined the Realtime channel")


def test_new_order_appears_without_reload(page: Page, base_url, menu):
    log_in(page)
    page.evaluate("window.loadedAt = performance.timeOrigin")

    place_order(base_url, menu["slot"], menu["dish"], "רונית אלון")
    realtime_change(base_url)

    row = page.locator(".order-cards li", has_text="רונית אלון")
    expect(row).to_be_visible()
    expect(page.locator(".nav-count")).to_have_text("1")
    expect(page.locator("#live-status")).to_have_text("רשימת ההזמנות עודכנה")
    # The same page, not a reload.
    assert page.evaluate("window.loadedAt === performance.timeOrigin")
    page.screenshot(path=SHOTS / "live-dashboard.png", full_page=True)


def test_open_order_is_not_replaced_by_a_live_update(page: Page, base_url, menu):
    page.get_by_role("button", name="פתיחת ההזמנה של רונית אלון").click()
    heading = page.get_by_role("heading", name="הזמנה של רונית אלון")
    expect(heading).to_be_visible()

    place_order(base_url, menu["slot"], menu["dish"], "עמית בר")
    realtime_change(base_url)

    expect(page.locator(".nav-count")).to_have_text("2")
    expect(heading).to_be_visible()


def test_no_javascript_errors(page: Page):
    assert page.errors == []
