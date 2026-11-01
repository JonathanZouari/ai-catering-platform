"""Walks a caterer through the dashboard in a real browser. Tests run in order on one session."""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from conftest import SHOTS

PNG_PATH = Path(__file__).parent / "fixtures" / "dish.png"
XSS_NAME = "<img src=x onerror=window.pwned=1>"


def save(page: Page, label: str, text: str) -> None:
    field = page.get_by_label(label, exact=True)
    field.fill(text)


def notice(page: Page):
    return page.locator("#notice")


def submit_dialog(page: Page) -> None:
    page.locator("dialog button[type=submit]").click()


def test_page_is_hebrew_rtl(page: Page):
    page.goto("/admin/")
    assert page.locator("html").get_attribute("lang") == "he"
    assert page.locator("html").get_attribute("dir") == "rtl"


def test_wrong_password_shows_hebrew_error(page: Page):
    save(page, "אימייל", "owner@example.com")
    save(page, "סיסמה", "wrong")
    page.get_by_role("button", name="כניסה").click()
    expect(notice(page)).to_have_text("האימייל או הסיסמה שגויים")


def test_login_shows_empty_menu(page: Page):
    save(page, "סיסמה", "right")
    page.get_by_role("button", name="כניסה").click()
    expect(page.get_by_text("אין הזמנות להצגה")).to_be_visible()
    page.get_by_role("link", name="תפריט").click()
    expect(page.get_by_text("עדיין אין קטגוריות")).to_be_visible()


def test_create_category(page: Page):
    page.get_by_role("button", name="קטגוריה חדשה").click()
    save(page, "שם", "סלטים")
    submit_dialog(page)
    expect(page.get_by_role("heading", name="סלטים")).to_be_visible()


def test_create_dish_with_dietary_data_and_image(page: Page):
    page.get_by_role("button", name="מנה חדשה").click()
    save(page, "שם המנה", "טבולה")
    save(page, "מחיר בש״ח", "120.50")
    page.get_by_label("כשרות", exact=True).select_option("pareve")
    page.get_by_label("גלוטן", exact=True).select_option("contains")
    page.get_by_label("תמונה", exact=True).set_input_files(PNG_PATH)
    page.screenshot(path=SHOTS / "dish-form.png")
    submit_dialog(page)

    row = page.locator(".rows li", has_text="טבולה")
    expect(row).to_contain_text("₪120.50")
    expect(row).to_contain_text("כשרות: פרווה")
    expect(row).to_contain_text("קלוריות: לא צוין")


def test_dish_survives_reload_and_keeps_unknown_allergens(page: Page):
    page.reload()
    page.locator(".rows li", has_text="טבולה").get_by_role("button", name="עריכה").click()
    expect(page.get_by_label("גלוטן", exact=True)).to_have_value("contains")
    expect(page.get_by_label("סויה", exact=True)).to_have_value("unknown")
    expect(page.get_by_label("כשרות", exact=True)).to_have_value("pareve")
    expect(page.locator("dialog img.preview")).to_be_visible()
    assert page.locator("dialog img.preview").evaluate("img => img.naturalWidth") > 0
    page.get_by_role("button", name="ביטול").click()


def test_dish_name_cannot_inject_html(page: Page):
    page.get_by_role("button", name="מנה חדשה").click()
    save(page, "שם המנה", XSS_NAME)
    save(page, "מחיר בש״ח", "1")
    submit_dialog(page)
    expect(page.locator(".rows li", has_text=XSS_NAME)).to_be_visible()
    assert page.evaluate("window.pwned") is None
    page.locator(".rows li", has_text=XSS_NAME).get_by_role("button", name="מחיקה").click()
    submit_dialog(page)
    expect(page.locator(".rows li", has_text=XSS_NAME)).to_have_count(0)


def test_backend_validation_reaches_the_user_and_form_stays_open(page: Page):
    page.get_by_role("button", name="מנה חדשה").click()
    save(page, "שם המנה", "בשר צלוי")
    save(page, "מחיר בש״ח", "10")
    page.get_by_label("תמחור", exact=True).select_option("per_weight")
    submit_dialog(page)
    expect(notice(page)).to_have_class("notice error")
    expect(page.locator("dialog")).to_be_visible()
    save(page, "תיאור יחידה", "ק״ג")
    submit_dialog(page)
    expect(page.locator(".rows li", has_text="בשר צלוי")).to_be_visible()


def test_category_with_dishes_cannot_be_deleted(page: Page):
    page.locator("section", has_text="סלטים").get_by_role("button", name="מחיקה").first.click()
    submit_dialog(page)
    expect(notice(page)).to_have_text("אי אפשר למחוק קטגוריה שיש בה מנות")
    page.get_by_role("button", name="ביטול").click()
    expect(page.get_by_role("heading", name="סלטים")).to_be_visible()


def test_time_slots_and_blocked_dates(page: Page):
    page.get_by_role("link", name="זמינות").click()
    page.get_by_role("button", name="חלון זמן חדש").click()
    save(page, "משעה", "09:00")
    save(page, "עד שעה", "12:00")
    page.get_by_label("יום", exact=True).select_option("4")
    submit_dialog(page)
    expect(page.locator(".rows li", has_text="יום חמישי")).to_contain_text("09:00–12:00")

    save(page, "תאריך", "2027-04-22")
    save(page, "סיבה", "פסח")
    page.get_by_role("button", name="חסימת תאריך").click()
    expect(page.locator(".rows li", has_text="פסח")).to_be_visible()


def test_delivery_zones(page: Page):
    page.get_by_role("link", name="משלוחים").click()
    page.get_by_role("button", name="אזור חדש").click()
    save(page, "שם האזור", "מרכז")
    save(page, "דמי משלוח בש״ח", "50")
    save(page, "ערים", "תל אביב\nרמת גן")
    submit_dialog(page)
    expect(page.locator(".rows li", has_text="מרכז")).to_contain_text("תל אביב, רמת גן")


def test_quantity_rule_can_be_changed_and_reverted(page: Page):
    page.get_by_role("link", name="כמויות").click()
    form = page.get_by_role("form", name="סלטים")
    expect(form).to_contain_text("ברירת מחדל")
    form.get_by_label("מנות למבוגר: סלטים").fill("2.5")
    form.get_by_role("button", name="שמירה").click()
    expect(notice(page)).to_have_text("הכמויות נשמרו")
    form = page.get_by_role("form", name="סלטים")
    expect(form).not_to_contain_text("ברירת מחדל")
    expect(form.get_by_label("מנות למבוגר: סלטים")).to_have_value("2.5")

    form.get_by_role("button", name="חזרה לברירת המחדל").click()
    expect(page.get_by_role("form", name="סלטים")).to_contain_text("ברירת מחדל")


def test_profile_saves_kashrut_settings(page: Page):
    page.get_by_role("link", name="פרופיל העסק").click()
    expect(page.get_by_text("/c/taamim/")).to_be_visible()
    save(page, "סטטוס כשרות", "כשר בהשגחת הרבנות")
    page.get_by_label("הזמנה שמערבת בשר וחלב").select_option("block")
    page.get_by_role("button", name="שמירה").click()
    expect(notice(page)).to_have_text("הפרטים נשמרו")
    page.get_by_label("לוגו").set_input_files(PNG_PATH)
    expect(page.locator("img.preview")).to_be_visible()

    page.reload()
    expect(page.get_by_label("סטטוס כשרות")).to_have_value("כשר בהשגחת הרבנות")
    expect(page.get_by_label("הזמנה שמערבת בשר וחלב")).to_have_value("block")


@pytest.mark.parametrize(
    "screen", ["orders", "menu", "availability", "delivery", "quantities", "profile"]
)
def test_no_sideways_scroll_on_phone(page: Page, screen: str):
    page.goto(f"/admin/#{screen}")
    page.wait_for_load_state("networkidle")
    page.screenshot(path=SHOTS / f"{screen}.png", full_page=True)
    width = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    assert width[0] <= width[1], f"{screen} overflows"


def test_no_javascript_errors(page: Page):
    assert page.errors == []


def test_logout_returns_to_login(page: Page):
    page.get_by_role("button", name="יציאה").click()
    expect(page.get_by_role("heading", name="כניסה לניהול העסק")).to_be_visible()
