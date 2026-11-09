import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PAGES = ("/", "/customer/", "/admin/", "/accessibility/")


@pytest.mark.parametrize("path", PAGES)
def test_page_loads_accessibility_toolbar(path):
    html = client.get(path).text
    assert "/js/a11y.js" in html
    assert "/css/a11y.css" in html


@pytest.mark.parametrize("path", ["/", "/customer/"])
def test_pages_link_to_statement(path):
    assert 'href="/accessibility/"' in client.get(path).text


def test_statement_page_has_required_sections():
    html = client.get("/accessibility/").text
    assert 'lang="he"' in html
    assert "5568" in html
    for heading in ("כיצד מפעילים את כלי הנגישות", "פנייה בנושא נגישות"):
        assert heading in html


@pytest.mark.parametrize("path", ["/js/a11y.js", "/css/a11y.css", "/css/statement.css"])
def test_toolbar_assets_served(path):
    assert client.get(path).status_code == 200
