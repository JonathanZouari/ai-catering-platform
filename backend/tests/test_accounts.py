# ruff: noqa: F811, F401  (fixtures imported from test_orders)
import inspect
import uuid

import pytest
from sqlalchemy import text

from app.agents import tools as agent_tools
from app.core.storage import clean_name
from app.schemas.orders import OrderOut

from .test_orders import body, no_minimum, slot  # noqa: F401  (fixtures)
from .test_security import api_routes, error_code

A_ID, B_ID = str(uuid.uuid4()), str(uuid.uuid4())
JPEG = b"\xff\xd8\xff" + b"0" * 100
PDF = b"%PDF-1.4 " + b"0" * 100


@pytest.fixture
def bearer(make_token):
    def make(sub, **kw):
        token = make_token(role=None, sub=sub, email=f"{sub}@example.com", **kw)
        return {"Authorization": f"Bearer {token}"}

    return make


@pytest.fixture
def a(bearer):
    return bearer(A_ID)


@pytest.fixture
def b(bearer):
    return bearer(B_ID)


def place(client, body, headers):
    r = client.post("/api/orders", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ---- auth
def test_me_creates_customer_and_rejects_anonymous_users(client, a, bearer):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers=bearer(A_ID, is_anonymous=True)).status_code == 401
    me = client.get("/api/me", headers=a)
    assert me.status_code == 200 and me.json()["email"] == f"{A_ID}@example.com"
    assert me.json()["avatar_url"] is None
    assert client.get("/api/me", headers=a).json()["id"] == me.json()["id"]


def test_anonymous_user_cannot_create_order_with_account(client, body, bearer):
    r = client.post("/api/orders", json=body, headers=bearer(A_ID, is_anonymous=True))
    assert r.status_code == 401 and error_code(r) == "unauthenticated"


def test_customer_tokens_blocked_from_admin_routes(client, a):
    for route in api_routes():
        path = getattr(route, "path", "")
        if path.startswith("/api/admin") and "{" not in path:
            for method in route.methods - {"HEAD", "OPTIONS"}:
                assert client.request(method, path, headers=a).status_code == 403, path


def test_me_patch_and_orders_list(client, a, body):
    created = place(client, body, a)
    assert (
        client.patch("/api/me", json={"full_name": "New Name"}, headers=a).json()["full_name"]
        == "New Name"
    )
    orders = client.get("/api/me/orders", headers=a).json()
    assert [o["id"] for o in orders] == [created["id"]]


# ---- order access
def test_guest_flow_unchanged(client, body):
    created = place(client, body, {})
    h = {"X-Order-Token": created["access_token"]}
    assert client.get(f"/api/orders/{created['id']}", headers=h).status_code == 200
    assert client.get(f"/api/orders/{created['id']}").status_code == 404
    # a stale or garbage bearer must not break the private link
    both = h | {"Authorization": "Bearer garbage"}
    assert client.get(f"/api/orders/{created['id']}", headers=both).status_code == 200


def test_owner_can_open_order_but_customer_b_cannot(client, body, a, b):
    order = place(client, body, a)
    url = f"/api/orders/{order['id']}"
    assert client.get(url, headers=a).status_code == 200
    assert client.get(f"{url}/pricing", headers=a).status_code == 200
    denied = client.get(url, headers=b)
    missing = client.get(f"/api/orders/{uuid.uuid4()}", headers=b)
    assert denied.status_code == 404 and denied.json() == missing.json()
    # B holding a valid token for a *different* order gets nothing for A's order
    other = place(client, body, b)
    h = b | {"X-Order-Token": other["access_token"]}
    assert client.get(url, headers=h).status_code == 404
    assert client.get(f"{url}/files", headers=b).status_code == 404


def test_order_made_before_accounts_is_not_linked_by_email(client, body, a, db):
    body["customer"]["email"] = f"{A_ID}@example.com"  # same address as account A
    guest = place(client, body, {})
    assert client.get("/api/me/orders", headers=a).json() == []
    assert client.get(f"/api/orders/{guest['id']}", headers=a).status_code == 404
    token = {"X-Order-Token": guest["access_token"]}
    assert client.get(f"/api/orders/{guest['id']}", headers=token).status_code == 200


def test_files_not_visible_to_agents():
    assert "files" not in OrderOut.model_fields
    assert "files" not in inspect.getsource(agent_tools).lower().replace("profiles", "")


# ---- avatar
def avatar(client, headers, data=JPEG, name="me.jpg"):
    return client.post("/api/me/avatar", files={"file": (name, data)}, headers=headers)


def test_avatar_upload_private_signed_replace_and_delete(client, a, objects):
    r = avatar(client, a)
    assert r.status_code == 200
    assert "customer-avatars" in r.json()["avatar_url"] and "exp=300" in r.json()["avatar_url"]
    first = next(iter(objects))
    assert first[0] == "customer-avatars"
    avatar(client, a)
    assert first not in objects and len(objects) == 1  # replaced object removed
    assert client.delete("/api/me/avatar", headers=a).json()["avatar_url"] is None
    assert objects == {}


def test_avatar_validation(client, a, b, objects):
    assert avatar(client, a, b"").status_code == 415
    assert avatar(client, a, b"MZ\x90\x00" + b"0" * 50, "cat.jpg").status_code == 415
    assert (
        avatar(client, a, b"<svg xmlns='http://www.w3.org/2000/svg'/>", "a.svg").status_code == 415
    )
    assert avatar(client, a, PDF, "a.pdf").status_code == 415
    assert avatar(client, a, JPEG + b"0" * (5 * 1024 * 1024)).status_code == 413
    assert objects == {}


def test_avatar_upload_failure_keeps_no_row_and_delete_failure_keeps_row(
    client, a, objects, storage_fail
):
    storage_fail.add("upload")
    assert avatar(client, a).status_code == 502
    storage_fail.clear()
    avatar(client, a)
    storage_fail.add("delete")
    assert client.delete("/api/me/avatar", headers=a).status_code == 502
    storage_fail.clear()
    assert client.get("/api/me", headers=a).json()["avatar_url"] is not None
    assert len(objects) == 1


def test_customer_cannot_touch_another_customers_avatar(client, a, b, objects):
    avatar(client, a)
    r = client.get("/api/me", headers=b)
    assert r.json()["avatar_url"] is None  # B only ever sees their own
    client.delete("/api/me/avatar", headers=b)
    assert len(objects) == 1


# ---- order files
def upload(client, order, headers, data=JPEG, name="menu.jpg"):
    return client.post(
        f"/api/orders/{order['id']}/files", files={"file": (name, data)}, headers=headers
    )


def test_order_files_roundtrip_with_token_and_owner(client, body, a, objects):
    order = place(client, body, a)
    r = upload(client, order, a, PDF, "plan.pdf")
    assert r.status_code == 201 and r.json()["content_type"] == "application/pdf"
    assert r.json()["url"].startswith("https://signed.test/order-files/")
    assert any(bucket == "order-files" for bucket, _ in objects)
    listed = client.get(f"/api/orders/{order['id']}/files", headers=a).json()
    assert [f["original_name"] for f in listed] == ["plan.pdf"]
    # the guest-style private link works too
    token = {"X-Order-Token": order["access_token"]}
    assert client.get(f"/api/orders/{order['id']}/files", headers=token).status_code == 200
    gone = client.delete(f"/api/orders/{order['id']}/files/{listed[0]['id']}", headers=a)
    assert gone.status_code == 204 and objects == {}


def test_order_file_other_customer_blocked(client, body, a, b, objects):
    order = place(client, body, a)
    file_id = upload(client, order, a).json()["id"]
    assert upload(client, order, b).status_code == 404
    assert client.delete(f"/api/orders/{order['id']}/files/{file_id}", headers=b).status_code == 404
    assert client.get(f"/api/orders/{order['id']}/files").status_code == 404
    assert len(objects) == 1


def test_order_file_validation(client, body, a, objects):
    order = place(client, body, a)
    assert upload(client, order, a, b"").status_code == 415
    assert upload(client, order, a, b"MZ\x90\x00" + b"0" * 50, "cat.jpg").status_code == 415
    assert upload(client, order, a, b"<svg/>", "a.svg").status_code == 415
    assert upload(client, order, a, b"<html></html>", "a.html").status_code == 415
    assert upload(client, order, a, PDF + b"0" * (10 * 1024 * 1024)).status_code == 413
    assert objects == {}
    # between the image and file caps a PDF is fine
    assert upload(client, order, a, PDF + b"0" * (6 * 1024 * 1024), "big.pdf").status_code == 201


def test_hostile_filename_is_sanitised(client, body, a):
    order = place(client, body, a)
    name = "../../etc/passwd\x00<script>alert(1)</script>" + "x" * 500 + ".jpg"
    stored = upload(client, order, a, JPEG, name).json()["original_name"]
    assert len(stored) <= 100 and "/" not in stored and "\x00" not in stored
    assert clean_name("C:\\evil\\cmd.exe") == "cmd.exe" and clean_name("") == "file"


def test_eleventh_file_rejected(client, body, a, objects):
    order = place(client, body, a)
    for _ in range(10):
        assert upload(client, order, a).status_code == 201
    r = upload(client, order, a)
    assert r.status_code == 409 and error_code(r) == "file_limit"
    assert len(objects) == 10


def test_order_file_upload_failure_leaves_no_row(client, body, a, storage_fail, db):
    order = place(client, body, a)
    storage_fail.add("upload")
    assert upload(client, order, a).status_code == 502
    assert db.execute(text("SELECT count(*) FROM order_files")).scalar() == 0


def test_order_file_delete_failure_keeps_row(client, body, a, storage_fail):
    order = place(client, body, a)
    file_id = upload(client, order, a).json()["id"]
    storage_fail.add("delete")
    assert client.delete(f"/api/orders/{order['id']}/files/{file_id}", headers=a).status_code == 502
    assert len(client.get(f"/api/orders/{order['id']}/files", headers=a).json()) == 1


# ---- admin + category photo
def test_admin_order_files_and_category_image(admin, client, body, a, objects):
    order = place(client, body, a)
    upload(client, order, a)
    url = f"/api/admin/orders/{order['id']}/files"
    assert len(admin.get(url).json()) == 1
    assert admin.post(url, files={"file": ("x.pdf", PDF)}).json()["uploaded_by"] == "admin"
    cat = admin.post("/api/admin/categories", json={"name_he": "קינוחים"}).json()
    r = admin.post(
        f"/api/admin/categories/{cat['id']}/image",
        files={"file": ("c.png", b"\x89PNG\r\n\x1a\n" + b"0" * 9)},
    )
    assert r.status_code == 200 and r.json()["image_path"].startswith("categories/")
    assert ("dish-images", r.json()["image_path"]) in objects
    assert (
        admin.post(
            f"/api/admin/categories/{cat['id']}/image", files={"file": ("c.svg", b"<svg/>")}
        ).status_code
        == 415
    )
