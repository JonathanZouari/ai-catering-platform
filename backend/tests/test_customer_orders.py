import copy
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


def payload(delivery=False):
    return {
        "contact": {"name": "בדיקת הזמנה", "phone": "0501234567"},
        "event": {
            "type": "יום הולדת",
            "date": (datetime.now(ZoneInfo("Asia/Jerusalem")) + timedelta(days=20))
            .date()
            .isoformat(),
            "slot": "09:00-11:00" if delivery else "10:00-12:00",
            "fulfillment": "delivery" if delivery else "pickup",
            "city": "תל אביב-יפו" if delivery else "",
            "address": "רחוב הבדיקה 12" if delivery else "",
            "adults": 10,
            "children": 2,
            "vegetarian": 1,
            "vegan": 0,
            "restricted": 0,
            "notes": "בדיקת שמירה",
        },
        "items": {"d1": 2, "d5": 1.5},
        "expected_total_minor": 34100 if delivery else 28100,
    }


def credentials():
    return {"X-Order-Token": secrets.token_hex(32)}


@pytest.mark.parametrize("delivery", [False, True])
def test_submit_read_retry_and_privacy(isolated_settings, delivery):
    headers = credentials()
    body = payload(delivery)
    with TestClient(app) as client:
        response = client.post("/api/orders", json=body, headers=headers)
        assert response.status_code == 201, response.text
        saved = response.json()
        assert saved["status"] == "pending_approval"
        assert saved["snapshot"]["total"] == body["expected_total_minor"] / 100
        assert saved["event"] == body["event"]
        assert len(saved["snapshot"]["lines"]) == 2
        retry = client.post("/api/orders", json=body, headers=headers)
        assert retry.status_code == 200
        assert retry.json() == saved
        url = f"/api/orders/{saved['id']}"
        assert client.get(url, headers=headers).json() == saved
        assert client.get("/api/orders/receipt", headers=headers).json() == saved
        assert client.get("/api/orders/receipt", headers=credentials()).status_code == 404
        assert client.get(url, headers=credentials()).status_code == 404
        assert client.get(url).status_code == 422
        changed = copy.deepcopy(body)
        changed["contact"]["name"] = "different"
        assert client.post("/api/orders", json=changed, headers=headers).status_code == 409
    with sqlite3.connect(isolated_settings) as db:
        assert db.execute("SELECT count(*) FROM orders").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM order_items").fetchone()[0] == 2
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert (
            db.execute("SELECT token_hash FROM order_submissions").fetchone()[0]
            != headers["X-Order-Token"]
        )
        db.execute("UPDATE dishes SET price_minor=999999 WHERE id='d1'")
    with TestClient(app) as client:
        assert client.get(url, headers=headers).json() == saved


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda p: p.update(expected_total_minor=1), 409),
        (lambda p: p.update(items={"missing": 1}), 422),
        (lambda p: p.update(items={"d1": -1}), 422),
        (lambda p: p.update(items={"d5": 0.7}), 422),
        (lambda p: p["event"].update(slot="bad"), 422),
        (lambda p: p["event"].update(adults=0), 422),
        (lambda p: p["event"].update(vegan=100), 422),
        (lambda p: p["event"].update(date="2000-01-01"), 422),
        (
            lambda p: p["event"].update(fulfillment="delivery", city="unknown", slot="09:00-11:00"),
            422,
        ),
        (lambda p: p["contact"].update(phone="bad"), 422),
    ],
)
def test_rejected_input_writes_nothing(isolated_settings, mutation, code):
    body = payload()
    mutation(body)
    with TestClient(app) as client:
        assert client.post("/api/orders", json=body, headers=credentials()).status_code == code
    with sqlite3.connect(isolated_settings) as db:
        for table in ("customers", "events", "addresses", "orders", "order_items"):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0  # noqa: S608


def test_failure_mid_write_rolls_back(isolated_settings):
    with TestClient(app, raise_server_exceptions=False) as client:
        with sqlite3.connect(isolated_settings) as db:
            db.execute(
                "CREATE TRIGGER fail_line BEFORE INSERT ON order_items "
                "BEGIN SELECT RAISE(ABORT, 'test failure'); END"
            )
        response = client.post("/api/orders", json=payload(True), headers=credentials())
        assert response.status_code == 500
    with sqlite3.connect(isolated_settings) as db:
        for table in ("customers", "addresses", "events", "orders"):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0  # noqa: S608


def test_concurrent_retry_creates_one_order():
    with TestClient(app) as client:
        headers = credentials()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda _: client.post("/api/orders", json=payload(), headers=headers), range(2)
                )
            )
        assert sorted(r.status_code for r in results) == [200, 201]
        assert results[0].json()["id"] == results[1].json()["id"]


def test_real_server_process_restart_preserves_order(isolated_settings):
    """Two separate server processes, same file, fresh HTTP client after restart."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    root = Path(__file__).resolve().parents[1]
    env = os.environ | {"SQLITE_PATH": str(isolated_settings), "DB_AUTO_MIGRATE": "true"}
    headers = credentials()
    saved = None
    for run in range(2):
        process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
                for _ in range(100):
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    assert process.poll() is None, "server exited before startup"
                    time.sleep(0.1)
                else:
                    pytest.fail("server startup timed out")
                if run == 0:
                    response = client.post("/api/orders", json=payload(True), headers=headers)
                    assert response.status_code == 201, response.text
                    saved = response.json()
                else:
                    response = client.get(f"/api/orders/{saved['id']}", headers=headers)
                    assert response.status_code == 200
                    assert response.json() == saved
        finally:
            process.terminate()
            process.wait(timeout=10)
