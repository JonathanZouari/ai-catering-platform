import pytest

from app.core import storage
from app.core.config import get_settings
from app.services import catalog as svc
from tests.conftest import AUTH
from tests.test_catalog import make_dish

JPG = b"\xff\xd8\xff\xe0" + b"0" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 100


@pytest.fixture
def bucket(monkeypatch):
    """Fake Supabase Storage: records uploads and deletes."""
    files = {"uploaded": [], "deleted": []}
    monkeypatch.setattr(get_settings(), "supabase_url", "https://proj.supabase.co")
    monkeypatch.setattr(storage, "upload", lambda p, d, t: files["uploaded"].append((p, t)))
    monkeypatch.setattr(storage, "delete", lambda p: files["deleted"].append(p) or True)
    return files


def put(client, dish_id, data, ctype, headers=AUTH, **params):
    return client.put(
        f"/api/admin/dishes/{dish_id}/image",
        content=data,
        headers={**headers, "Content-Type": ctype},
        params=params,
    )


def test_upload_replace_and_remove(client, bucket):
    _, dish = make_dish(client)
    res = put(client, dish["id"], JPG, "image/jpeg")
    assert res.status_code == 200, res.text
    first = res.json()
    assert first["image_path"].startswith(f"dishes/{dish['id']}/") and first["image_path"].endswith(
        ".jpg"
    )
    assert first["image_url"] == (
        f"https://proj.supabase.co/storage/v1/object/public/dish-images/{first['image_path']}"
    )
    assert first["image_is_placeholder"] is False
    # the public menu shows the same URL
    public = client.get("/api/catalog/dishes").json()[0]
    assert public["image_url"] == first["image_url"]

    second = put(client, dish["id"], WEBP, "image/webp").json()
    assert second["image_path"] != first["image_path"] and second["image_path"].endswith(".webp")
    assert bucket["deleted"] == [first["image_path"]]  # the replaced file is removed

    gone = client.delete(f"/api/admin/dishes/{dish['id']}/image", headers=AUTH).json()
    assert gone["image_path"] is None and gone["image_url"] is None
    assert bucket["deleted"][-1] == second["image_path"]


def test_placeholder_is_flagged(client, bucket):
    _, dish = make_dish(client)
    out = put(client, dish["id"], PNG, "image/png", placeholder="true").json()
    assert out["image_path"].startswith("placeholder/") and out["image_is_placeholder"] is True


def test_rejects_non_images_and_wrong_types(client, bucket):
    _, dish = make_dish(client)
    for data, ctype in [
        (b"<svg onload=alert(1)>", "image/svg+xml"),  # SVG can carry script
        (b"<html>", "text/html"),
        (b"not really a jpeg", "image/jpeg"),  # the bytes must match the claimed type
        (PNG, "image/jpeg"),
    ]:
        res = put(client, dish["id"], data, ctype)
        assert res.status_code == 422 and res.json()["error"]["code"] == "invalid_image", ctype
    assert bucket["uploaded"] == []


def test_size_limit(client, bucket):
    _, dish = make_dish(client)
    big = JPG + b"0" * svc.MAX_IMAGE_BYTES
    res = put(client, dish["id"], big, "image/jpeg")
    assert res.status_code == 413 and res.json()["error"]["code"] == "image_too_large"
    assert bucket["uploaded"] == []


def test_owner_only_and_unknown_dish(client, bucket):
    _, dish = make_dish(client)
    assert put(client, dish["id"], JPG, "image/jpeg", headers={}).status_code == 401
    bad = {"Authorization": "Bearer wrong"}
    assert put(client, dish["id"], JPG, "image/jpeg", headers=bad).status_code == 401
    other = "00000000-0000-0000-0000-000000000000"
    assert put(client, other, JPG, "image/jpeg").status_code == 404
    assert bucket["uploaded"] == []


def test_storage_not_configured(client, monkeypatch):
    _, dish = make_dish(client)
    monkeypatch.setattr(get_settings(), "supabase_service_role_key", None)
    res = put(client, dish["id"], JPG, "image/jpeg")
    assert res.status_code == 503 and res.json()["error"]["code"] == "storage_unavailable"


def test_static_asset_paths_stay_relative(client):
    _, dish = make_dish(client)
    assert svc._image_url("/assets/img/cake.jpg") == "/assets/img/cake.jpg"
    assert svc._image_url(None) is None
