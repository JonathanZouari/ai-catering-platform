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
        "/customer/menu/",
        "/customer/order/",
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
        "/js/menu.js",
        "/js/order-status.js",
        "/js/assistant.js",
        "/assets/img/table.jpg",
    )
    for path in paths:
        assert client.get(path).status_code == 200, path


def test_static_files_revalidate():
    # A deploy must show up at once: browsers keep the file but re-check it (304 when unchanged).
    for path in ("/", "/css/base.css", "/js/event.js", "/assets/img/table.jpg"):
        first = client.get(path)
        assert first.headers["cache-control"] == "no-cache", path
        again = client.get(path, headers={"If-None-Match": first.headers["etag"]})
        assert again.status_code == 304, path
        assert again.headers["cache-control"] == "no-cache", path
    assert "no-cache" not in client.get("/health").headers.get("cache-control", "")


def test_city_list_served():
    # tools/build_cities.py output: the city field suggests these, served cities get a fee.
    response = client.get("/data/cities.json")
    assert response.status_code == 200
    cities = response.json()
    assert len(cities) > 1000
    assert cities == sorted(set(cities))
    assert all(isinstance(c, str) and c == c.strip() and c for c in cities)
    assert not [c for c in cities if "שבט" in c]
    assert {"תל אביב - יפו", "אילת", "קרית אונו"} <= set(cities)


def test_webp_dish_photos_have_image_type():
    res = client.get("/assets/img/d-hummus.webp")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/webp"
