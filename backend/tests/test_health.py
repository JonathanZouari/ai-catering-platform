from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_database():
    with TestClient(app) as client:  # runs the startup migration
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == {"engine": "sqlite", "schema_version": "0001", "foreign_keys": True}


def test_health_is_503_when_schema_missing(monkeypatch):
    monkeypatch.setenv("DB_AUTO_MIGRATE", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "error"


def test_frontend_pages_served():
    with TestClient(app) as client:
        for path in ("/", "/customer/", "/admin/"):
            response = client.get(path)
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
