from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_frontend_pages_served():
    for path in (
        "/",
        "/customer/",
        "/customer/event/",
        "/admin/",
        "/admin/availability/",
        "/admin/orders/",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert '<html lang="he" dir="rtl"' in response.text


def test_design_assets_served():
    paths = (
        "/css/base.css",
        "/css/home.css",
        "/js/illustrations.js",
        "/js/motion.js",
        "/js/home.js",
        "/js/admin.js",
        "/js/admin-common.js",
        "/js/admin-availability.js",
        "/js/admin-orders.js",
        "/js/account.js",
        "/js/customer-session.js",
        "/js/event.js",
        "/assets/img/table.jpg",
    )
    for path in paths:
        assert client.get(path).status_code == 200, path
