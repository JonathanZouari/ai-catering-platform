"""Create (or promote) the business owner's login.  Run from backend/:

    python scripts/create_admin.py owner@example.com            # generates a password and prints it
    python scripts/create_admin.py owner@example.com --password "..."

Public sign-up is disabled in Supabase, so this script (server-side secret key) is the only way
to create an account. It sets app_metadata.role = "admin", which the backend checks on every call.
"""

import argparse
import secrets
import string
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.auth import ADMIN_ROLE  # noqa: E402
from app.core.config import get_settings  # noqa: E402


def generate_password() -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(16))
        if any(c.isdigit() for c in pw) and any(c.isalpha() for c in pw):
            return pw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    parser.add_argument("--password", help="at least 10 characters with letters and digits")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        sys.exit("SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env")
    password = args.password or generate_password()
    email = args.email.strip().lower()
    body = {"password": password, "email_confirm": True, "app_metadata": {"role": ADMIN_ROLE}}

    with httpx.Client(
        base_url=f"{settings.supabase_url}/auth/v1/admin",
        headers={"apikey": settings.supabase_secret_key},
        timeout=20,
    ) as client:
        created = client.post("/users", json={"email": email, **body})
        if created.status_code == 422 and "email_exists" in created.text:
            listing = client.get("/users", params={"per_page": 1000}).raise_for_status()
            users = listing.json()["users"]
            user = next(u for u in users if (u.get("email") or "").lower() == email)
            client.put(f"/users/{user['id']}", json=body).raise_for_status()
            action = "Updated existing user"
        else:
            if created.is_error:
                sys.exit(f"Supabase refused: {created.status_code} {created.text}")
            action = "Created user"

    print(f"{action} {email} with role '{ADMIN_ROLE}'.")
    if not args.password:
        print(f"Generated password: {password}")


if __name__ == "__main__":
    main()
