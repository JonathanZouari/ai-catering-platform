"""Browser end-to-end tests: the real app served by uvicorn, driven by Playwright.

Run from backend/:  uv run --env-file ../.env pytest tests/e2e
Locally without downloaded browsers, add  --browser-channel chrome  to use the installed Chrome.
"""

import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

CUSTOMER_EMAIL = "demo@example.com"
OWNER_EMAIL = "owner@example.com"

needs_supabase = pytest.mark.skipif(
    not all(
        os.environ.get(k)
        for k in (
            "SUPABASE_URL",
            "SUPABASE_PUBLISHABLE_KEY",
            "DEMO_CUSTOMER_PASSWORD",
            "DEMO_OWNER_PASSWORD",
        )
    ),
    reason="needs the dev Supabase project and demo-user passwords in the environment",
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url():
    """Starts the app once per session; overrides pytest-base-url so page.goto('/x') works."""
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(  # noqa: S603 - fixed argv, no user input
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            try:
                if httpx.get(f"{url}/health").status_code == 200:
                    break
            except httpx.TransportError:
                time.sleep(0.2)
        else:
            raise RuntimeError("uvicorn did not start")
        yield url
    finally:
        server.terminate()
        server.wait(timeout=10)


def login(page, email: str, password: str, next_path: str = "") -> None:
    page.goto(f"/login/{'?next=' + next_path if next_path else ''}")
    page.get_by_label("אימייל").fill(email)
    page.get_by_label("סיסמה").fill(password)
    page.locator("#auth-submit").click()


@pytest.fixture
def customer_page(page):
    login(page, CUSTOMER_EMAIL, os.environ["DEMO_CUSTOMER_PASSWORD"])
    page.wait_for_url("**/customer/**")
    return page


@pytest.fixture
def owner_page(page):
    login(page, OWNER_EMAIL, os.environ["DEMO_OWNER_PASSWORD"])
    page.wait_for_url("**/admin/**")
    return page
