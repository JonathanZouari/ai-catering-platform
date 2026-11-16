from fastapi.testclient import TestClient

from app.core.config import Settings
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


def test_public_config_exposes_only_public_values(monkeypatch):
    settings = Settings(
        supabase_url="https://x.supabase.co",
        supabase_publishable_key="sb_publishable_x",
        supabase_service_role_key="secret-value",
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    response = client.get("/api/public-config")
    assert response.status_code == 200
    assert response.json() == {
        "supabaseUrl": "https://x.supabase.co",
        "supabasePublishableKey": "sb_publishable_x",
    }
