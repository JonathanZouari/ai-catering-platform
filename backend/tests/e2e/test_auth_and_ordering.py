"""Login, role routing and the first ordering step against the dev Supabase project.

Read-only for the database: the order draft lives in the browser until it is submitted.
"""

import datetime as dt
import re

from playwright.sync_api import expect

from tests.e2e.conftest import CUSTOMER_EMAIL, login, needs_supabase

pytestmark = needs_supabase


def test_customer_page_requires_login(page):
    page.goto("/customer/")
    page.wait_for_url(re.compile(r"/login/\?next=%2Fcustomer%2F"))
    expect(page.get_by_role("heading", name="כניסה לחשבון")).to_be_visible()


def test_empty_login_shows_error(page):
    page.goto("/login/")
    page.locator("#auth-submit").click()
    expect(page.get_by_role("alert")).to_have_text("הזינו אימייל וסיסמה.")


def test_wrong_password_shows_error(page):
    login(page, CUSTOMER_EMAIL, "definitely-not-the-password")
    expect(page.get_by_role("alert")).to_have_text("האימייל או הסיסמה שגויים.")


def test_customer_fills_event_and_reaches_menu(customer_page):
    page = customer_page
    expect(page.get_by_role("heading", name="ספרו לנו על האירוע")).to_be_visible()

    # Submitting with no occasion and no date shows inline errors and stays on the step.
    page.get_by_role("button", name="המשך לתפריט").click()
    expect(page.locator("#err-type")).to_be_visible()
    expect(page.locator("#err-date")).to_be_visible()

    # Keyboard, not a click: the sticky header overlaps the cards after Playwright's scroll.
    birthday = page.get_by_role("radio", name="יום הולדת")
    birthday.focus()
    page.keyboard.press("Space")
    expect(birthday).to_be_checked()
    page.locator("#f-date").fill((dt.date.today() + dt.timedelta(days=14)).isoformat())
    page.locator("#f-slot").select_option(index=1)
    page.get_by_role("button", name="המשך לתפריט").click()

    expect(page.get_by_role("heading", name="בחרו מנות לתפריט")).to_be_visible()
    expect(page).to_have_url(re.compile(r"#menu$"))


def test_occasion_link_preselects_event_type(customer_page):
    page = customer_page
    page.goto("/customer/?occasion=ארוחת שבת")
    expect(page.get_by_role("radio", name="ארוחת שבת")).to_be_checked()


def test_customer_cannot_use_admin(customer_page):
    page = customer_page
    page.goto("/admin/")
    expect(page.get_by_role("alert")).to_have_text("לחשבון הזה אין הרשאת ניהול.")


def test_owner_lands_on_dashboard(owner_page):
    page = owner_page
    expect(page.get_by_role("heading", name="ממשק העסק")).to_be_visible()
    expect(page.get_by_role("heading", name="בקשות להצעת מחיר")).to_be_visible()
    expect(page.get_by_role("heading", name="מנות ותמונות")).to_be_visible()


def test_sign_out_returns_to_login(owner_page):
    page = owner_page
    page.get_by_role("button", name="יציאה").click()
    page.wait_for_url("**/login/")
    page.goto("/admin/")
    page.wait_for_url(re.compile(r"/login/\?next="))
