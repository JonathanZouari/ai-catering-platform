from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_cloud_config_only_exposes_publishable_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co/")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-secret-not-for-browser")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/api/cloud-config")
    assert response.json() == {
        "configured": True,
        "url": "https://example.supabase.co",
        "publishableKey": "sb_publishable_test",
    }
    assert "server-secret" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_cloud_config_rejects_accidental_secret_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_secret_wrong-field")
    get_settings.cache_clear()
    with TestClient(app) as client:
        body = client.get("/api/cloud-config").json()
    assert body == {"configured": False, "url": None, "publishableKey": None}
