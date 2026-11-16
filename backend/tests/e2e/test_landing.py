"""Public landing page. Needs no Supabase."""

from playwright.sync_api import expect


def test_landing_page_renders(page):
    page.goto("/")
    expect(page.locator("h1").first).to_be_visible()
    cta = page.get_by_role("link", name="תכננו את האירוע").first
    expect(cta).to_have_attribute("href", "/customer/")


def test_occasion_cards_link_to_customer_with_occasion(page):
    page.goto("/")
    hrefs = page.locator("a.occasion-card").evaluate_all("els => els.map(e => e.href)")
    assert len(hrefs) == 6
    assert all("/customer/?occasion=" in h for h in hrefs)
