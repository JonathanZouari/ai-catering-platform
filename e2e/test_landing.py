"""The public home page, on a phone and on a computer."""

import pytest
from playwright.sync_api import Page, expect

from conftest import SHOTS

COMPUTER = {"width": 1366, "height": 860}
PHONE = {"width": 390, "height": 844}
SIZES = [PHONE, COMPUTER]


def set_guests(page: Page, value: int) -> None:
    page.locator("#guests").evaluate(
        "(slider, value) => {"
        "slider.value = value;"
        "slider.dispatchEvent(new Event('input', {bubbles: true}));"
        "}",
        value,
    )


def show_step(page: Page, number: int) -> None:
    page.locator(f".step[data-step='{number}']").evaluate(
        "step => {"
        "const line = window.innerWidth < 960 ? 0.6 : 0.5 - step.offsetHeight / 2 / innerHeight;"
        "const top = step.getBoundingClientRect().top + scrollY - innerHeight * line;"
        "window.scrollTo({top, behavior: 'instant'});"
        "}"
    )
    expect(page.locator("#stage")).to_have_attribute("data-step", str(number))


@pytest.mark.parametrize("size", SIZES, ids=["phone", "computer"])
def test_page_fits_loads_everything_and_has_no_errors(page: Page, size):
    page.set_viewport_size(size)
    failed = []
    page.on("response", lambda r: failed.append(r.url) if r.status >= 400 else None)

    page.goto("/")
    page.wait_for_load_state("networkidle")

    assert page.locator("html").get_attribute("lang") == "he"
    assert page.locator("html").get_attribute("dir") == "rtl"
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert page.evaluate("document.fonts.check('700 20px Heebo', 'א')")
    assert failed == []
    assert page.errors == []


@pytest.mark.parametrize("size", SIZES, ids=["phone", "computer"])
def test_every_story_stage_fits_and_is_shown(page: Page, size):
    page.set_viewport_size(size)
    page.goto("/")
    page.wait_for_timeout(1000)
    page.screenshot(path=SHOTS / f"landing-{size['width']}-hero.png")

    for number in (1, 2, 3, 4):
        show_step(page, number)
        page.wait_for_timeout(650)
        page.screenshot(path=SHOTS / f"landing-{size['width']}-step{number}.png")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    expect(page.locator(".stamp")).to_have_css("opacity", "0.92")
    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    page.screenshot(path=SHOTS / f"landing-{size['width']}.png", full_page=True)


def test_guest_count_reprints_the_ticket(page: Page):
    page.goto("/")
    expect(page.locator("#ticket-total")).to_have_text("₪1,730")

    set_guests(page, 100)

    expect(page.locator("#guests-value")).to_have_text("100")
    expect(page.locator("#ticket-event")).to_have_text("יום הולדת · 100 אורחים")
    expect(page.locator("#ticket-lines li").first).to_contain_text("10 מגשים")
    expect(page.locator("#ticket-total")).to_have_text("₪4,370")


def test_event_type_changes_the_ticket_and_works_by_keyboard(page: Page):
    page.goto("/")

    page.locator("input[value=birthday]").focus()
    page.keyboard.press("ArrowDown")

    expect(page.locator("input[value=brit]")).to_be_checked()
    expect(page.locator("#ticket-event")).to_contain_text("ברית")
    expect(page.locator("#ticket-lines")).to_contain_text("דג אפוי")


def test_sample_figures_are_marked_as_samples(page: Page):
    page.goto("/")
    expect(page.locator(".ticket-note")).to_contain_text("הדגמה בלבד")
    expect(page.locator(".ticket-total")).to_contain_text("לדוגמה")


def test_reduced_motion_shows_the_finished_ticket(page: Page):
    page.emulate_media(reduced_motion="reduce")
    page.goto("/")
    assert page.locator("#ticket").evaluate("t => getComputedStyle(t).animationName") == "none"
    page.emulate_media(reduced_motion="no-preference")


def test_without_javascript_the_page_still_reads(page: Page, base_url):
    context = page.context.browser.new_context(java_script_enabled=False)
    tab = context.new_page()
    tab.goto(base_url)

    expect(tab.locator("h1")).to_be_visible()
    expect(tab.locator("#ticket-total")).to_have_text("₪1,730")
    expect(tab.locator(".step").first).to_be_visible()
    context.close()


def test_home_page_leads_to_the_caterer_login(page: Page):
    page.set_viewport_size(PHONE)
    page.goto("/")

    expect(page.locator("h1")).to_contain_text("הזמנה מסודרת")
    page.locator(".hero .button").click()

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
