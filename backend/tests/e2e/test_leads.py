"""Lead form on the landing page and in the menu step, and the owner's scored lead list.

The form's POST is intercepted, so these tests never write a lead to the server.
"""

import datetime as dt
import json
import re

from playwright.sync_api import expect

from tests.e2e.conftest import needs_supabase


def fill_lead_form(page, prefix: str) -> None:
    page.locator(f"#{prefix}-name").fill("בדיקה אוטומטית")
    page.locator(f"#{prefix}-phone").fill("050-0000002")
    page.locator(f"#{prefix}-type").select_option("יום הולדת")
    page.locator(f"#{prefix}-guests").fill("30")
    page.locator(f"#{prefix}-date").fill((dt.date.today() + dt.timedelta(days=21)).isoformat())
    page.locator(f"#{prefix}-budget").fill("120")
    page.locator(f"#{prefix}-consent").check()


def capture_lead_post(page) -> list[dict]:
    sent: list[dict] = []

    def handle(route):
        sent.append(json.loads(route.request.post_data))
        route.fulfill(status=201, content_type="application/json", body='{"ok": true}')

    page.route("**/api/leads", handle)
    return sent


def test_landing_form_sends_details_and_signals(page):
    sent = capture_lead_post(page)
    page.goto("/?utm_source=instagram")
    fill_lead_form(page, "landing-lead")
    page.get_by_role("button", name="שליחה").click()
    expect(page.get_by_text("תודה! הפרטים התקבלו")).to_be_visible()
    assert sent[0]["source"] == "instagram"
    assert sent[0]["visits"] == 1
    assert sent[0]["consent"] is True
    assert {"dishes_viewed", "minutes_on_site", "used_chat"} <= sent[0].keys()


def test_landing_form_needs_consent(page):
    sent = capture_lead_post(page)
    page.goto("/")
    fill_lead_form(page, "landing-lead")
    page.locator("#landing-lead-consent").uncheck()
    page.get_by_role("button", name="שליחה").click()
    expect(page.get_by_text("תודה! הפרטים התקבלו")).not_to_be_visible()
    assert sent == []


@needs_supabase
def test_menu_form_counts_dishes_seen(customer_page):
    page = customer_page
    sent = capture_lead_post(page)
    birthday = page.get_by_role("radio", name="יום הולדת")
    birthday.focus()
    page.keyboard.press("Space")
    page.locator("#f-date").fill((dt.date.today() + dt.timedelta(days=14)).isoformat())
    page.locator("#f-slot").select_option(index=1)
    page.get_by_role("button", name="המשך לתפריט").click()
    expect(page).to_have_url(re.compile(r"#menu$"))

    # Scroll through the catalog so dish cards come on screen.
    for _ in range(12):
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(150)
    fill_lead_form(page, "menu-lead")
    page.locator("#menu-lead-title").scroll_into_view_if_needed()
    page.locator(".lead-form button[type=submit]").click()
    expect(page.get_by_text("תודה! הפרטים התקבלו")).to_be_visible()
    assert sent[0]["dishes_viewed"] > 0


@needs_supabase
def test_owner_sees_leads_with_probability(owner_page):
    page = owner_page
    expect(page.get_by_role("heading", name="לידים לפי סיכוי להזמנה")).to_be_visible()
    first = page.locator("#leads-title ~ ul > li").first
    expect(first).to_contain_text(re.compile(r"\d+% סיכוי להזמין"))
    expect(page.get_by_text("ליד חם").first).to_be_visible()


FAKE_SUPABASE = "https://leadsdemo.supabase.co"
FAKE_LEADS = [
    {
        "lead_id": "L-1",
        "full_name": "נועה כהן",
        "phone": "050-0001111",
        "event_type": "בר או בת מצווה",
        "guests": 80,
        "days_until_event": 25,
        "budget_per_guest": 150,
        "dishes_viewed": 18,
        "visits": 3,
        "source": "referral",
        "used_chat": True,
        "probability": 0.62,
        "is_hot": True,
        "is_demo": True,
    },
    {
        "lead_id": "L-2",
        "full_name": "דני לוי",
        "phone": "050-0002222",
        "event_type": "ארוחת שבת",
        "guests": 12,
        "days_until_event": 120,
        "budget_per_guest": 80,
        "dishes_viewed": 1,
        "visits": 1,
        "source": "instagram",
        "used_chat": False,
        "probability": 0.04,
        "is_hot": False,
        "is_demo": True,
    },
]


def test_owner_dashboard_renders_leads_offline(page):
    """Runs without a Supabase project: the session, the database and the lead API are faked
    in the browser, so this checks only how the dashboard shows the scored leads."""
    page.route(
        "**/api/public-config",
        lambda r: r.fulfill(
            json={"supabaseUrl": FAKE_SUPABASE, "supabasePublishableKey": "sb_publishable_fake"}
        ),
    )
    page.route(f"{FAKE_SUPABASE}/**", lambda r: r.fulfill(json=[]))
    seen_auth: list[str] = []

    def leads(route):
        seen_auth.append(route.request.headers.get("authorization", ""))
        route.fulfill(json=FAKE_LEADS)

    page.route("**/api/admin/leads", leads)
    session = {
        "access_token": "fake-owner-token",
        "refresh_token": "r",
        "token_type": "bearer",
        "expires_in": 3600,
        "expires_at": int(dt.datetime.now().timestamp()) + 3600,
        "user": {"id": "owner", "aud": "authenticated", "app_metadata": {"role": "admin"}},
    }
    page.add_init_script(
        f"localStorage.setItem('sb-leadsdemo-auth-token', {json.dumps(json.dumps(session))});"
    )
    page.goto("/admin/")
    expect(page.get_by_role("heading", name="לידים לפי סיכוי להזמנה")).to_be_visible()
    cards = page.locator("#leads-title ~ ul > li")
    expect(cards).to_have_count(2)
    expect(cards.nth(0)).to_contain_text("62% סיכוי להזמין")
    expect(cards.nth(0)).to_contain_text("ליד חם")
    expect(cards.nth(0)).to_contain_text("הגיע מהמלצה, דיבר עם העוזר")
    expect(cards.nth(1)).to_contain_text("4% סיכוי להזמין")
    expect(cards.nth(1)).not_to_contain_text("ליד חם")
    assert seen_auth == ["Bearer fake-owner-token"]
