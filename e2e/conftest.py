import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

SHOTS = Path(os.environ.get("E2E_SCREENSHOTS", Path(__file__).parent / "screenshots"))
PHONE = {"width": 390, "height": 844}


def call(base_url, path, body=None, token=None, method="POST", headers=None):
    all_headers = {"Content-Type": "application/json"} | (headers or {})
    if token:
        all_headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(  # noqa: S310
        f"{base_url}{path}", data=json.dumps(body).encode(), headers=all_headers, method=method
    )
    with urllib.request.urlopen(request) as response:  # noqa: S310
        return json.loads(response.read() or "null")


@pytest.fixture(scope="module")
def base_url():
    """A fresh server and database for each test file."""
    url = os.environ.get("E2E_DATABASE_URL", "")
    if "test" not in url.rsplit("/", 1)[-1]:
        pytest.fail("E2E_DATABASE_URL must be set and its database name must contain 'test'")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = Path(__file__).parent / "server.py"
    process = subprocess.Popen([sys.executable, str(server), str(port)])  # noqa: S603
    address = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(f"{address}/health")  # noqa: S310
            break
        except OSError:
            time.sleep(0.2)
    else:
        process.kill()
        pytest.fail("server did not start")
    yield address
    process.kill()


@pytest.fixture(scope="module")
def page(base_url):
    SHOTS.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport=PHONE, base_url=base_url, permissions=["clipboard-read", "clipboard-write"]
        )
        tab = context.new_page()
        tab.errors = []
        tab.on("pageerror", lambda error: tab.errors.append(str(error)))
        yield tab
        browser.close()
