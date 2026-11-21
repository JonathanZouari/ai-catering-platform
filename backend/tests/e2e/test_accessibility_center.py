"""Accessibility center on a public page. Needs no Supabase."""

from playwright.sync_api import expect


def open_center(page):
    fab = page.locator("#a11y-fab")
    fab.focus()
    page.keyboard.press("Enter")
    expect(fab).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_role("heading", name="מרכז נגישות")).to_be_visible()
    return fab


def test_center_opens_and_closes_by_keyboard(page):
    page.goto("/")
    fab = open_center(page)
    page.keyboard.press("Escape")
    expect(fab).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#a11y-panel")).to_be_hidden()
    expect(fab).to_be_focused()


def test_settings_apply_persist_and_reset(page):
    page.goto("/")
    open_center(page)
    page.get_by_label("ניגודיות גבוהה").check()
    page.get_by_label("גדול מאוד").check()
    html = page.locator("html")
    expect(html).to_have_class("js a11y-contrast a11y-text-xl")
    body_bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert body_bg == "rgb(255, 255, 255)"

    # Another page keeps the settings.
    page.goto("/accessibility/")
    expect(html).to_have_class("a11y-contrast a11y-text-xl")
    open_center(page)
    expect(page.get_by_label("ניגודיות גבוהה")).to_be_checked()

    page.get_by_role("button", name="איפוס ההגדרות").click()
    expect(html).not_to_have_class("a11y-contrast")
    expect(page.get_by_label("רגיל")).to_be_checked()


def test_no_mode_adds_filter_or_transform_above_the_button(page):
    """A filter or transform on an ancestor can pin a fixed button to the page instead of the
    screen in some browsers, so every mode must leave html, body and the center's box clean."""
    page.goto("/")
    open_center(page)
    for label in (
        "ניגודיות גבוהה",
        "הדגשת קישורים וכפתורים",
        "גופן קריא",
        "ריווח טקסט מוגדל",
        "סימון בולט של מיקוד המקלדת",
        "עצירת אנימציות",
        "גדול מאוד",
    ):
        page.get_by_label(label).check()
    styles = page.evaluate("""() => [document.documentElement, document.body,
        document.querySelector('.a11y-center')].map(el => {
          const s = getComputedStyle(el);
          return [s.filter, s.transform, s.perspective];
        })""")
    assert styles == [["none", "none", "none"]] * 3
