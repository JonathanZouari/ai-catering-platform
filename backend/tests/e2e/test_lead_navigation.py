"""Standalone lead-demo navigation, without external auth or customer data."""

import pytest
from playwright.sync_api import expect


@pytest.mark.parametrize("width", [320, 1280])
def test_lead_navigation_targets_and_keyboard(page, width):
    # Isolate the static admin link from the unrelated Supabase login flow.
    page.route(
        "**/js/admin/main.js", lambda route: route.fulfill(body="", content_type="text/javascript")
    )
    page.set_viewport_size({"width": width, "height": 740})
    page.goto("/admin/")
    for href in ("/admin/leads-demo/", "/admin/"):
        link = page.locator(f'a.nav-link[href="{href}"]')
        expect(link).to_be_visible()
        box = link.bounding_box()
        assert box and box["height"] >= 44 and box["width"] >= 44
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.keyboard.press("Tab")
        expect(link).to_be_focused()
        assert link.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
        page.keyboard.press("Enter")
        page.wait_for_url(f"**{href}")
    page.locator('a.nav-link[href="/admin/leads-demo/"]').click()
    page.wait_for_url("**/admin/leads-demo/")
    page.go_back()
    expect(page.locator('a.nav-link[href="/admin/leads-demo/"]')).to_be_visible()
    page.go_forward()
    expect(page.locator('a.nav-link[href="/admin/"]')).to_be_visible()
