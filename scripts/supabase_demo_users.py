"""Demo users, buckets and dish photos for the `cateringproject` Supabase project ONLY.

Run from backend/ after the migrations and database/supabase/demo_seed.sql, with the project's
values exported from .env:  uv run python ../scripts/supabase_demo_users.py
Safe to re-run. New passwords are appended to .env and never printed.
"""

import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path

import psycopg

REF = "xodugwmoeuinkkjqflsr"  # refuses to run against any other project
ROOT = Path(__file__).resolve().parents[1]
URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
DB = os.environ["DATABASE_URL"].replace("+psycopg", "")
if f"{REF}.supabase.co" not in URL or REF not in DB:
    raise SystemExit("These settings are not the cateringproject project")

IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"]
BUCKETS = [
    ("dish-images", True, 5 * 1024 * 1024, IMAGE_TYPES),
    ("customer-avatars", False, 5 * 1024 * 1024, IMAGE_TYPES),
    ("order-files", False, 10 * 1024 * 1024, [*IMAGE_TYPES, "application/pdf"]),
]
CATEGORY_IMAGES = {
    "Salads": "food-salad",
    "Mains": "food-main",
    "Sides": "food-sides",
    "Fish": "food-fish",
    "Desserts": "food-dessert",
    "Drinks": "food-lemonade",
}


def call(method, path, body=None, content_type="application/json", extra=None):
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    headers = {"apikey": KEY, "Content-Type": content_type, **(extra or {})}
    if KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {KEY}"
    request = urllib.request.Request(URL + path, data=data, headers=headers, method=method)  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"null")


def ensure_user(email, env_name, app_metadata):
    _, listing = call("GET", "/auth/v1/admin/users?per_page=200")
    found = next((u for u in listing["users"] if u["email"] == email), None)
    if found:
        call("PUT", f"/auth/v1/admin/users/{found['id']}", {"app_metadata": app_metadata})
        return found["id"]
    password = secrets.token_urlsafe(18)
    status, user = call(
        "POST",
        "/auth/v1/admin/users",
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "app_metadata": app_metadata,
        },
    )
    if status >= 300:
        raise SystemExit(f"Could not create {email}: {status}")
    with (ROOT / ".env").open("a") as env:
        env.write(f"{env_name}={password}\n")
    return user["id"]


ensure_user("owner@example.com", "OWNER_DEMO_PASSWORD", {"role": "admin"})
customer_id = ensure_user("customer@example.com", "CUSTOMER_DEMO_PASSWORD", {})

for name, public, limit, types in BUCKETS:
    status, _ = call(
        "POST",
        "/storage/v1/bucket",
        {
            "id": name,
            "name": name,
            "public": public,
            "file_size_limit": limit,
            "allowed_mime_types": types,
        },
    )
    print("bucket", name, "created" if status < 300 else f"not created ({status})")

with psycopg.connect(DB) as conn:
    linked = conn.execute(
        "UPDATE customers SET auth_user_id = %s WHERE email = 'customer@example.com'",
        (customer_id,),
    ).rowcount
    print("customer rows linked:", linked)
    rows = conn.execute(
        "SELECT c.id, c.name_en, d.id FROM dish_categories c LEFT JOIN dishes d "
        "ON d.category_id = c.id ORDER BY c.sort_order"
    ).fetchall()
    uploaded = set()
    for category_id, category, dish_id in rows:
        stem = CATEGORY_IMAGES[category]
        path = f"demo/{stem}.webp"
        if path not in uploaded:
            data = (ROOT / "frontend/assets/menu-categories" / f"{stem}.webp").read_bytes()
            status, _ = call(
                "POST",
                f"/storage/v1/object/dish-images/{path}",
                data,
                "image/webp",
                {"x-upsert": "true"},
            )
            if status >= 300:
                raise SystemExit(f"Upload failed for {path}: {status}")
            uploaded.add(path)
        conn.execute(
            "UPDATE dish_categories SET image_path = %s WHERE id = %s", (path, category_id)
        )
        if dish_id:
            conn.execute("UPDATE dishes SET image_path = %s WHERE id = %s", (path, dish_id))
    print("images uploaded:", len(uploaded))
