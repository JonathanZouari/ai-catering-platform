"""End-to-end flows in a real browser against the dev Supabase project."""

import datetime as dt
import re
import uuid

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import NEEDS_SUPABASE, URL

pytestmark = NEEDS_SUPABASE


def random_phone() -> str:
    return "05" + str(uuid.uuid4().int)[:8]


@pytest.fixture
def cleanup_phones(service):
    phones: list[str] = []
    yield phones
    for phone in phones:
        service.delete("/rest/v1/leads", params={"phone": f"eq.{phone}"}).raise_for_status()


def lead_rows(service: httpx.Client, phone: str) -> list[dict]:
    return service.get(
        "/rest/v1/leads", params={"select": "full_name,guests,status", "phone": f"eq.{phone}"}
    ).json()


# ---------- landing page and lead form ----------


def test_lead_form_validates_submits_and_blocks_duplicates(
    page: Page, base_url, service, cleanup_phones
):
    page.goto(f"{base_url}/#contact")
    page.click("#lead-form button[type=submit]")
    expect(page.locator("#err-lead-name")).to_be_visible()
    expect(page.locator("#err-lead-phone")).to_be_visible()
    expect(page.locator("#lead-name")).to_be_focused()

    phone = random_phone()
    cleanup_phones.append(phone)
    page.fill("#lead-name", "בדיקת קצה לקצה")
    page.fill("#lead-phone", f"{phone[:3]}-{phone[3:]}")  # typed with a dash, stored as digits
    page.fill("#lead-guests", "70")
    page.fill("#lead-date", (dt.date.today() + dt.timedelta(days=20)).isoformat())
    page.click("#lead-form button[type=submit]")
    expect(page.locator("#lead-status")).to_have_text(re.compile("תודה"))
    expect(page.locator("#lead-name")).to_have_value("")
    assert lead_rows(service, phone) == [
        {"full_name": "בדיקת קצה לקצה", "guests": 70, "status": "new"}
    ]

    page.fill("#lead-name", "בדיקת כפילות")
    page.fill("#lead-phone", phone)
    page.click("#lead-form button[type=submit]")
    expect(page.locator("#lead-status")).to_have_text(re.compile("כבר קיבלנו פנייה"))
    assert len(lead_rows(service, phone)) == 1


def test_landing_fits_a_phone_screen(page: Page, base_url):
    page.set_viewport_size({"width": 375, "height": 800})
    page.goto(f"{base_url}/#contact")
    expect(page.locator("#lead-form")).to_be_visible()
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0, f"page scrolls sideways by {overflow}px"


def test_accessibility_statement_linked_from_landing(page: Page, base_url):
    page.goto(base_url)
    page.get_by_role("link", name="הצהרת נגישות").click()
    expect(page.locator("h1")).to_contain_text("הצהרת נגישות")


# ---------- sign-in and access ----------


def test_signed_out_visitor_is_sent_to_login(page: Page, base_url):
    page.goto(f"{base_url}/customer/")
    expect(page).to_have_url(re.compile(r"/login/\?next="))


def test_wrong_password_shows_error(page: Page, base_url):
    page.goto(f"{base_url}/login/")
    page.fill("#auth-email", "demo@example.com")
    page.fill("#auth-password", "not-the-password")
    page.click("#auth-submit")
    expect(page.locator("#auth-error")).to_have_text("האימייל או הסיסמה שגויים.")


def test_customer_cannot_open_admin(page: Page, login, base_url):
    login("demo@example.com", "/admin/")
    expect(page.get_by_role("alert")).to_have_text("לחשבון הזה אין הרשאת ניהול.")
    expect(page.locator("#leads-title")).to_have_count(0)


def test_customer_order_flow_loads_menu_from_database(page: Page, login):
    login("demo@example.com")
    expect(page).to_have_url(re.compile("/customer/"))
    expect(page.locator("#app")).to_contain_text("איזה אירוע מתכננים?")
    expect(page.get_by_text("לא הצלחנו לטעון את התפריט")).to_have_count(0)


# ---------- owner dashboard ----------


def test_owner_sees_ranked_leads_and_updates_status(page: Page, login, service, cleanup_phones):
    phone = random_phone()
    cleanup_phones.append(phone)
    event_date = (dt.date.today() + dt.timedelta(days=15)).isoformat()
    service.post(
        "/rest/v1/leads",
        json={
            "full_name": "ליד E2E חם",
            "phone": phone,
            "guests": 150,
            "event_type": "בדיקה",
            "email": "e2e@example.com",
            "event_date": event_date,
        },
    ).raise_for_status()

    login("owner@example.com")
    expect(page).to_have_url(re.compile("/admin/"))
    leads = page.locator("[aria-labelledby=leads-title] .admin-list > li")
    expect(leads.first).to_contain_text("לחזור היום")

    card = leads.filter(has_text="ליד E2E חם")
    expect(card).to_contain_text("אירוע גדול מאוד")
    expect(card.get_by_role("link", name="WhatsApp")).to_have_attribute(
        "href", f"https://wa.me/972{phone[1:]}"
    )
    card.get_by_label("סטטוס").select_option("contacted")
    for _ in range(50):
        if lead_rows(service, phone)[0]["status"] == "contacted":
            break
        page.wait_for_timeout(100)
    assert lead_rows(service, phone)[0]["status"] == "contacted"

    page.reload()
    expect(
        page.locator("[aria-labelledby=leads-title] .admin-list > li").filter(has_text="ליד E2E חם")
    ).to_contain_text("במעקב")


def test_new_lead_appears_live_on_owner_dashboard(page: Page, login, cleanup_phones):
    login("owner@example.com")
    expect(page.locator("#leads-title")).to_be_visible()
    page.wait_for_timeout(1500)  # let the Realtime channel subscribe

    phone = random_phone()
    cleanup_phones.append(phone)
    anon = {
        "apikey": page.evaluate("fetch('/api/public-config').then(r => r.json())")[
            "supabasePublishableKey"
        ]
    }
    httpx.post(
        f"{URL}/rest/v1/rpc/submit_lead",
        headers=anon,
        json={"payload": {"name": "ליד בזמן אמת", "phone": phone}},
    ).raise_for_status()
    expect(page.get_by_text("ליד בזמן אמת")).to_be_visible(timeout=10_000)
