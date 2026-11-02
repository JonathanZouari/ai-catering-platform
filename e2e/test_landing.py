"""The public home page, on a phone and on a computer."""

import pytest
from playwright.sync_api import Page, expect

from conftest import SHOTS

COMPUTER = {"width": 1366, "height": 860}
PHONE = {"width": 390, "height": 844}


@pytest.mark.parametrize("size", [PHONE, COMPUTER], ids=["phone", "computer"])
def test_page_fits_loads_everything_and_has_no_errors(page: Page, size):
    page.set_viewport_size(size)
    failed = []
    page.on("response", lambda r: failed.append(r.url) if r.status >= 400 else None)

    page.goto("/")
    page.wait_for_load_state("networkidle")
    for image in page.locator("img").all():
        image.scroll_into_view_if_needed()
        expect(image).to_have_js_property("complete", True)
        assert image.evaluate("element => element.naturalWidth") > 0

    assert page.locator("html").get_attribute("lang") == "he"
    assert page.locator("html").get_attribute("dir") == "rtl"
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert failed == []
    assert page.errors == []
    page.screenshot(path=SHOTS / f"landing-{size['width']}.png", full_page=True)


def test_home_page_leads_to_the_caterer_login(page: Page):
    page.set_viewport_size(PHONE)
    page.goto("/")

    expect(page.locator("h1")).to_contain_text("הזמנות קייטרינג")
    page.locator(".hero .login").click()

    assert page.url.endswith("/admin/")


def test_page_loads_nothing_from_other_sites(page: Page, base_url):
    outside = []
    page.on(
        "request",
        lambda request: (
            outside.append(request.url) if not request.url.startswith(base_url) else None
        ),
    )
    page.goto("/")
    page.wait_for_load_state("networkidle")

    assert outside == []
