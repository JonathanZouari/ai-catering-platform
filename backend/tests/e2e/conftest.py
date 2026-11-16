"""E2E fixtures: the real app on a local port, a browser, and the dev Supabase project.

Run from backend/:  uv run --env-file ../.env pytest tests/e2e
First time only:    uv run playwright install chromium
"""

import os
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from app.main import app

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
PASSWORDS = {
    "demo@example.com": os.environ.get("DEMO_CUSTOMER_PASSWORD", ""),
    "owner@example.com": os.environ.get("DEMO_OWNER_PASSWORD", ""),
}

NEEDS_SUPABASE = pytest.mark.skipif(
    not (
        URL and SERVICE and os.environ.get("SUPABASE_PUBLISHABLE_KEY") and all(PASSWORDS.values())
    ),
    reason="needs Supabase credentials in the environment",
)


@pytest.fixture(scope="session")
def base_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("app did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def service():
    with httpx.Client(
        base_url=URL, headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"}
    ) as client:
        yield client


@pytest.fixture
def login(page, base_url):
    def sign_in(email: str, next_path: str = "") -> None:
        page.goto(f"{base_url}/login/{'?next=' + next_path if next_path else ''}")
        page.fill("#auth-email", email)
        page.fill("#auth-password", PASSWORDS[email])
        page.click("#auth-submit")

    return sign_in
