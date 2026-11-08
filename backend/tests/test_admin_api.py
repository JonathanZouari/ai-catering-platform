import pytest

from app.api import admin
from app.core import auth, storage
from app.core.auth import CurrentUser

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


@pytest.fixture
def uploads(monkeypatch):
    """Records Storage calls instead of reaching Supabase."""
    calls = {"upload": [], "remove": []}
    monkeypatch.setattr(storage, "upload", lambda *a: calls["upload"].append(a))
    monkeypatch.setattr(storage, "remove", lambda *a: calls["remove"].append(a))
    return calls


def as_user(monkeypatch, role):
    user = CurrentUser(id="u1", email="demo@example.test", role=role)
    monkeypatch.setattr(auth, "fetch_user", lambda token: user if token == "good" else None)
    return {"Authorization": "Bearer good"}


def first_dish_id(client):
    return client.get("/api/catalog/dishes").json()[0]["id"]


def post_image(client, dish_id, headers, data=PNG, content_type="image/png"):
    files = {"file": ("photo", data, content_type)}
    return client.post(f"/api/admin/dishes/{dish_id}/image", headers=headers, files=files)


def test_upload_requires_sign_in(client, uploads):
    response = post_image(client, first_dish_id(client), {})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    assert uploads["upload"] == []


def test_expired_token_rejected(client, uploads, monkeypatch):
    as_user(monkeypatch, "owner")
    response = post_image(client, first_dish_id(client), {"Authorization": "Bearer stale"})
    assert response.status_code == 401


def test_non_owner_forbidden(client, uploads, monkeypatch):
    headers = as_user(monkeypatch, None)
    response = post_image(client, first_dish_id(client), headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert uploads["upload"] == []


def test_owner_uploads_image(client, uploads, monkeypatch):
    headers = as_user(monkeypatch, "owner")
    dish_id = first_dish_id(client)
    response = post_image(client, dish_id, headers)
    assert response.status_code == 200
    body = response.json()
    assert body["image_path"].startswith(f"{dish_id}/") and body["image_path"].endswith(".png")
    bucket, path, data, content_type = uploads["upload"][0]
    assert (bucket, path, data, content_type) == (
        "dish-images",
        body["image_path"],
        PNG,
        "image/png",
    )
    # The public menu now carries the path.
    public = next(d for d in client.get("/api/catalog/dishes").json() if d["id"] == dish_id)
    assert public["image_path"] == body["image_path"]


def test_replacing_image_removes_old_object(client, uploads, monkeypatch):
    headers = as_user(monkeypatch, "owner")
    dish_id = first_dish_id(client)
    first = post_image(client, dish_id, headers).json()["image_path"]
    second = post_image(client, dish_id, headers, JPEG, "image/jpeg").json()["image_path"]
    assert second.endswith(".jpg") and second != first
    assert uploads["remove"] == [("dish-images", [first])]


@pytest.mark.parametrize(
    ("data", "content_type", "status"),
    [
        (b"%PDF-1.4", "application/pdf", 422),  # wrong type
        (b"not really a png", "image/png", 422),  # spoofed content type
        (PNG + b"\x00" * admin.MAX_IMAGE_BYTES, "image/png", 413),  # too large
    ],
)
def test_bad_files_rejected(client, uploads, monkeypatch, data, content_type, status):
    headers = as_user(monkeypatch, "owner")
    response = post_image(client, first_dish_id(client), headers, data, content_type)
    assert response.status_code == status
    assert uploads["upload"] == []


def test_unknown_dish(client, uploads, monkeypatch):
    headers = as_user(monkeypatch, "owner")
    response = post_image(client, "00000000-0000-0000-0000-000000000000", headers)
    assert response.status_code == 404


def test_admin_list_includes_unavailable(client, monkeypatch, engine):
    from sqlalchemy import update
    from sqlalchemy.orm import Session

    from app.models import Dish

    with Session(engine) as session, session.begin():
        session.execute(update(Dish).where(Dish.name == "חומוס ביתי").values(is_available=False))
    headers = as_user(monkeypatch, "owner")
    names = {d["name"] for d in client.get("/api/admin/dishes", headers=headers).json()}
    assert "חומוס ביתי" in names and len(names) == 17


def test_public_config_has_no_secret(client):
    body = client.get("/api/config").json()
    assert set(body) == {"supabase_url", "supabase_publishable_key"}
