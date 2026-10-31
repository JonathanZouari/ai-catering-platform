from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

DISH_CLIPS = (
    "schnitzel",
    "falafel",
    "noodles",
    "roast-roots",
    "leaf-radish-salad",
    "arabic-salad",
)


def test_customer_page_is_hebrew_rtl_with_preview_dialog():
    html = client.get("/customer/").text
    assert '<html lang="he" dir="rtl">' in html
    assert 'id="kitchen-preview"' in html
    assert "/js/customer/catalog.js" in html


def test_customer_prototype_assets_served():
    for path in (
        "/css/customer.css",
        "/js/customer/catalog.js",
        "/js/customer/demo-dishes.js",
        "/js/customer/kitchen-preview.js",
        "/js/customer/kitchen-scenes.js",
        "/js/customer/kitchen-sound.js",
        "/js/customer/hover-preview.js",
        "/js/customer/sound-pref.js",
        "/js/customer/video-segment.js",
    ):
        assert client.get(path).status_code == 200, path


def test_dish_videos_served_with_range_support_and_used_once():
    dishes_js = client.get("/js/customer/demo-dishes.js").text
    for name in DISH_CLIPS:
        path = f"/assets/video/{name}-preparation.mp4"
        response = client.get(path, headers={"Range": "bytes=0-1023"})
        assert response.status_code == 206, path  # seeking/segments need ranges
        assert response.headers["content-type"] == "video/mp4"
        # Each clip belongs to exactly one dish.
        assert dishes_js.count(path) == 1, path


def test_combined_noodles_clip_is_restricted_to_its_segment():
    dishes_js = client.get("/js/customer/demo-dishes.js").text
    line = next(ln for ln in dishes_js.splitlines() if "noodles-preparation.mp4" in ln)
    assert "startTime: 10.1" in line and "endTime: 20" in line


def test_customer_page_has_no_permanent_media_tiles():
    html = client.get("/customer/").text
    catalog_js = client.get("/js/customer/catalog.js").text
    assert "<video" not in catalog_js  # dish rows render no video/poster tiles
    assert html.count("<video") == 2  # hero loop + dialog player only
