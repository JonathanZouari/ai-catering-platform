"""Israeli accessibility regulations (2013, reg. 35) require a published accessibility statement.

These checks keep the statement page served, reachable from every page, and complete.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import FRONTEND_DIR, app

client = TestClient(app)

PAGES = ["/", "/customer/", "/login/", "/account/", "/admin/", "/accessibility/"]


@pytest.mark.parametrize("path", PAGES)
def test_page_links_to_statement_and_skips_to_content(path):
    html = client.get(path).text
    assert 'href="/accessibility/"' in html or path == "/accessibility/"
    skip = re.search(r'class="skip-link" href="#([\w-]+)"', html)
    assert skip, "missing skip link"
    assert f'id="{skip.group(1)}"' in html, "skip link points at a missing id"
    assert '<html lang="he" dir="rtl">' in html


def test_every_html_page_is_covered():
    found = {
        "/" + str(p.parent.relative_to(FRONTEND_DIR)).replace("\\", "/").strip(".") + "/"
        for p in FRONTEND_DIR.rglob("index.html")
    }
    found = {p.replace("//", "/") for p in found}
    assert found == set(PAGES)


def test_statement_has_required_sections():
    response = client.get("/accessibility/")
    assert response.status_code == 200
    html = response.text
    for text in (
        "ת״י 5568",
        "WCAG 2.0",
        "AA",
        "מגבלות ידועות",
        "פנייה בנושא נגישות",
        "רכז/ת נגישות",
    ):
        assert text in html, text
    assert re.search(r'<time datetime="\d{4}-\d{2}-\d{2}">', html), "missing last-updated date"
