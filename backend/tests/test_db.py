import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def seeded_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db(path)
    assert db.seed_db(path) is True
    return path


def test_seed_runs_once(seeded_db: Path):
    assert db.seed_db(seeded_db) is False
    with closing(db.get_connection(seeded_db)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM dishes").fetchone()[0] == len(db.DISHES)


def test_foreign_key_is_enforced(seeded_db: Path):
    with closing(db.get_connection(seeded_db)) as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO order_items (order_id, dish_id, quantity) VALUES (?, ?, ?)",
            (1, 9999, 1),
        )


def test_order_total_matches_items(seeded_db: Path):
    with closing(db.get_connection(seeded_db)) as conn:
        order = conn.execute(
            "SELECT subtotal, delivery_fee, total FROM orders WHERE id = 1"
        ).fetchone()
        items_sum = conn.execute(
            "SELECT SUM(snapshot_line_total) FROM order_items WHERE order_id = 1"
        ).fetchone()[0]
    assert order["subtotal"] == items_sum
    assert order["total"] == order["subtotal"] + order["delivery_fee"]


def test_menu_endpoint(seeded_db: Path):
    client = TestClient(app)
    response = client.get("/api/menu")
    assert response.status_code == 200
    categories = response.json()["categories"]
    assert [c["name"] for c in categories] == [name for name, _ in db.CATEGORIES]
    assert sum(len(c["dishes"]) for c in categories) == len(db.DISHES)
    cake = next(d for c in categories for d in c["dishes"] if d["name"] == "עוגת שוקולד")
    assert cake["is_vegan"] is None  # unknown stays unknown
    assert {"name": "גלוטן", "status": "contains"} in cake["allergens"]


def test_menu_endpoint_without_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "missing.db")
    response = TestClient(app).get("/api/menu")
    assert response.status_code == 503
