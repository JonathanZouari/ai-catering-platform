"""Admin leads section: open leads ranked by conversion score.

Set LEADS_SCREENSHOT_DIR to also save desktop and phone screenshots (used for PR assets).
"""

import os
import re
from pathlib import Path

from playwright.sync_api import expect

from tests.e2e.conftest import needs_supabase

pytestmark = needs_supabase


def _leads(page):
    heading = page.get_by_role("heading", name="לידים לפי סיכוי להזמנה")
    section = page.locator("section", has=heading)
    expect(section).to_be_visible()
    cards = section.locator(".admin-list > li.panel")
    expect(cards.first).to_be_visible()
    return section, cards


def test_leads_are_ranked_by_score_with_reasons_and_contact_links(owner_page):
    section, cards = _leads(owner_page)
    scores = [int(re.sub(r"\D", "", t)) for t in section.locator(".lead-score").all_inner_texts()]
    assert scores, "expected scored leads"
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)

    first = cards.first
    expect(first.locator(".badge").first).to_be_visible()
    expect(first.get_by_role("list", name="מה משפיע על ההערכה")).to_be_visible()
    tel = first.get_by_role("link", name=re.compile("התקשרות"))
    assert re.fullmatch(r"tel:\+972\d{8,9}", tel.get_attribute("href"))
    wa = first.get_by_role("link", name=re.compile("וואטסאפ"))
    assert re.fullmatch(r"https://wa\.me/972\d{8,9}", wa.get_attribute("href"))
    assert wa.get_attribute("rel") == "noopener noreferrer"


def test_synthetic_scores_are_labelled_as_demo(owner_page):
    section, _ = _leads(owner_page)
    expect(section.get_by_role("note")).to_contain_text("נתונים סינתטיים")


def test_closed_leads_are_not_listed(owner_page):
    section, _ = _leads(owner_page)
    expect(section.locator(".badge", has_text=re.compile("^(הומר|אבד)$"))).to_have_count(0)


def test_leads_fit_a_phone_screen(owner_page):
    page = owner_page
    page.set_viewport_size({"width": 390, "height": 844})
    _leads(page)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_screenshots_for_review(owner_page):
    target = os.environ.get("LEADS_SCREENSHOT_DIR")
    if not target:
        return
    page = owner_page
    out = Path(target)
    out.mkdir(parents=True, exist_ok=True)
    page.set_viewport_size({"width": 1280, "height": 1100})
    section, _ = _leads(page)
    page.add_style_tag(content="*{animation:none!important;transition:none!important}")
    section.evaluate("el => el.scrollIntoView()")
    page.screenshot(path=str(out / "leads-admin-desktop.png"))
    page.set_viewport_size({"width": 390, "height": 844})
    section.scroll_into_view_if_needed()
    page.screenshot(path=str(out / "leads-admin-phone.png"))
