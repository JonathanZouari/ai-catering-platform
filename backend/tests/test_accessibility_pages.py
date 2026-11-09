from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PAGES = ("/", "/customer/", "/admin/", "/accessibility/")


def test_accessibility_statement_served():
    response = client.get("/accessibility/")
    assert response.status_code == 200
    html = response.text
    assert '<html lang="he" dir="rtl">' in html
    # The sections Israeli regulations require in a statement (הצהרת נגישות).
    for heading in ("הצהרת נגישות", "מה עשינו כדי שהאתר יהיה נגיש", "איך משתמשים באתר",
                    "חלקים שאינם נגישים במלואם", "פנייה בנושא נגישות"):
        assert heading in html


def test_every_page_has_accessibility_menu():
    for path in PAGES:
        html = client.get(path).text
        assert '/css/a11y.css' in html, path
        assert '/js/lib/a11y-toolbar.js' in html, path


def test_landing_footer_links_to_statement():
    assert 'href="/accessibility/"' in client.get("/").text
