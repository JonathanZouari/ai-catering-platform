"""Run the whole app on this computer against the yummai-dev Supabase project.

    uv run python -m scripts.dev_server

Reads ../.env.supabase-dev (git-ignored) for the database, Auth and Storage settings.
Log in to the dashboard as demo@yummai.test with DEMO_PASSWORD from that file. To fill or
rebuild the demo caterer, run: uv run python -m scripts.seed_supabase ../.env.supabase-dev
"""

import os
from pathlib import Path

PORT = int(os.environ.get("PORT", "8000"))
ENV_FILE = Path(__file__).resolve().parents[2] / ".env.supabase-dev"
SETTINGS = ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY")


def load_env() -> None:
    if not ENV_FILE.exists():
        raise SystemExit(f"{ENV_FILE.name} is missing. It holds the yummai-dev keys.")
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    values = dict(line.split("=", 1) for line in lines if "=" in line)
    missing = [name for name in SETTINGS if not values.get(name)]
    if missing:
        raise SystemExit(f"{ENV_FILE.name} has no {', '.join(missing)}")
    for name in SETTINGS:
        os.environ[name] = values[name]
    os.environ.setdefault("SITE_CATERER", "taam")
    os.environ["APP_ENV"] = "development"


def main() -> None:
    load_env()
    import uvicorn

    print(f"Site:      http://127.0.0.1:{PORT}/")
    print(f"Dashboard: http://127.0.0.1:{PORT}/admin/  (demo@yummai.test, DEMO_PASSWORD)")
    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
