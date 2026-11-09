from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_frontend_pages_served():
    for path in ("/customer/", "/admin/"):
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


def test_accessibility_statement_served_and_linked():
    page = client.get("/accessibility/")
    assert page.status_code == 200
    assert 'lang="he"' in page.text and "הצהרת נגישות" in page.text
    for path in ("/", "/customer/"):
        assert 'href="/accessibility/"' in client.get(path).text
