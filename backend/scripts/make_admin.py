"""Grant (or revoke) the admin role for an existing Supabase Auth user.

The role lives in app_metadata, which only the service role can change.
The user must sign out and in again (or wait for token refresh) to get it.

Usage (from backend/):  uv run python scripts/make_admin.py owner@example.com [--revoke]
"""

import json
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, ".")
from app.core.config import get_settings  # noqa: E402


def _call(method: str, path: str, body: dict | None = None) -> dict:
    s = get_settings()
    if not (s.supabase_url and s.supabase_service_role_key):
        sys.exit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
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
        return json.loads(resp.read())


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    email = args[0].strip().lower()
    revoke = "--revoke" in sys.argv

    page = 1
    while True:
        users = _call("GET", f"/auth/v1/admin/users?page={page}&per_page=200")["users"]
        match = next((u for u in users if (u.get("email") or "").lower() == email), None)
        if match or len(users) < 200:
            break
        page += 1
    if not match:
        sys.exit(f"No user with email {email}. Sign up on the site first.")

    meta = dict(match.get("app_metadata") or {})
    if revoke:
        meta.pop("role", None)
    else:
        meta["role"] = "admin"
    path = f"/auth/v1/admin/users/{urllib.parse.quote(match['id'])}"
    _call("PUT", path, {"app_metadata": meta})
    print(f"{email}: admin {'revoked' if revoke else 'granted'}")


if __name__ == "__main__":
    main()
