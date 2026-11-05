"""Create (or reset) demo login accounts on the DEV Supabase project.

Creates one admin and one customer with confirmed emails and fresh random
passwords, and writes the credentials to ../demo-accounts.local.md (gitignored).
Re-running resets the passwords. Refuses to run unless APP_ENV=development.

Usage (from backend/):  uv run python scripts/create_demo_users.py
"""

import json
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")
from app.core.config import get_settings  # noqa: E402

DEMO_USERS = [
    {"email": "demo.admin@yumm.test", "full_name": "בעלת העסק (דמו)", "role": "admin"},
    {"email": "demo.customer@yumm.test", "full_name": "לקוחה לדוגמה", "role": None},
]
OUT_FILE = Path(__file__).resolve().parents[2] / "demo-accounts.local.md"


def _call(method: str, path: str, body: dict | None = None):
    s = get_settings()
    req = urllib.request.Request(  # noqa: S310 - URL comes from our own config
        s.supabase_url + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "apikey": s.supabase_service_role_key,
            "Authorization": f"Bearer {s.supabase_service_role_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        raw = resp.read()
        return json.loads(raw) if raw else None


def _find_user(email: str) -> dict | None:
    page = 1
    while True:
        users = _call("GET", f"/auth/v1/admin/users?page={page}&per_page=200")["users"]
        for u in users:
            if (u.get("email") or "").lower() == email:
                return u
        if len(users) < 200:
            return None
        page += 1


def main() -> None:
    s = get_settings()
    if s.app_env != "development":
        sys.exit("Refusing: demo users are for APP_ENV=development only.")
    if not (s.supabase_url and s.supabase_service_role_key):
        sys.exit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")

    rows = []
    for demo in DEMO_USERS:
        password = secrets.token_urlsafe(9)
        app_meta = {"role": demo["role"]} if demo["role"] else {}
        existing = _find_user(demo["email"])
        payload = {
            "password": password,
            "email_confirm": True,
            "app_metadata": app_meta,
            "user_metadata": {"full_name": demo["full_name"]},
        }
        if existing:
            _call("PUT", f"/auth/v1/admin/users/{existing['id']}", payload)
            action = "reset"
        else:
            _call("POST", "/auth/v1/admin/users", {"email": demo["email"], **payload})
            action = "created"
        rows.append((demo, password))
        print(f"{demo['email']}: {action}")

    lines = [
        "# Demo accounts (DEV only, do not commit)",
        "",
        f"Site: http://localhost:8000/login/  ·  Supabase project: {s.supabase_url}",
        "Re-run `uv run python scripts/create_demo_users.py` (from backend/) to reset passwords.",
        "",
        "| Role | Email | Password |",
        "|---|---|---|",
    ]
    for demo, password in rows:
        role = "admin (ממשק העסק)" if demo["role"] == "admin" else "customer (לקוח)"
        lines.append(f"| {role} | `{demo['email']}` | `{password}` |")
    OUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Credentials written to {OUT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        sys.exit(f"Supabase error {e.code}: {e.read().decode()[:300]}")
