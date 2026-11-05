from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_frontend_pages_served():
    for path in ("/customer/", "/admin/", "/login/"):
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


def test_public_config_never_exposes_service_role_key():
    body = client.get("/config/public").json()
    assert set(body) == {"supabase_url", "supabase_anon_key"}
