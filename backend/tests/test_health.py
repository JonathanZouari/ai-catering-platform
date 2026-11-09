from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_frontend_pages_served():
    for path in ("/customer/", "/admin/", "/accessibility/"):
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


def test_accessibility_statement_linked_from_every_page():
    # IS 5568 requires the statement to be reachable from every page.
    assert client.get("/accessibility/").status_code == 200
    for path in ("/", "/customer/", "/admin/"):
        assert 'href="/accessibility/"' in client.get(path).text, path
