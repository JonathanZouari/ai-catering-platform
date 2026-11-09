"""Create the demo customer and demo owner through the Supabase Admin API. Safe to re-run.

Run from backend/ before loading supabase/seed.sql:
    uv run --env-file ../.env python scripts/create_demo_users.py
"""

import json
import os
import urllib.error
import urllib.request

USERS = [
    {
        "email": "demo@example.com",
        "password_env": "DEMO_CUSTOMER_PASSWORD",
        "user_metadata": {"full_name": "לקוח דמו"},
        "app_metadata": {},
    },
    {
        "email": "owner@example.com",
        "password_env": "DEMO_OWNER_PASSWORD",
        "user_metadata": {"full_name": "בעל העסק דמו"},
        "app_metadata": {"role": "admin"},
    },
]


def create_user(base_url: str, key: str, user: dict) -> str:
    body = {
        "email": user["email"],
        "password": os.environ[user["password_env"]],
        "email_confirm": True,
        "user_metadata": user["user_metadata"],
        "app_metadata": user["app_metadata"],
    }
    request = urllib.request.Request(  # noqa: S310 - the URL comes from our own settings
        f"{base_url}/auth/v1/admin/users",
        data=json.dumps(body).encode(),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request):  # noqa: S310
            return "created"
    except urllib.error.HTTPError as error:
        if error.code == 422 and json.load(error).get("error_code") == "email_exists":
            return "already exists"
        raise


if __name__ == "__main__":
    url = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    for demo_user in USERS:
        print(demo_user["email"], create_user(url, secret, demo_user))
