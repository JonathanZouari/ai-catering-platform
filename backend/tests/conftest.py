import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.db import connect, migrate


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Every test gets its own SQLite file; the developer's database is never touched."""
    db_file = tmp_path / "test.sqlite3"
    monkeypatch.setenv("SQLITE_PATH", str(db_file))
    monkeypatch.setenv("DB_AUTO_MIGRATE", "true")
    get_settings.cache_clear()
    yield db_file
    get_settings.cache_clear()


@pytest.fixture
def db_path(isolated_settings: Path) -> Path:
    migrate(isolated_settings)
    return isolated_settings


@pytest.fixture
def conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(db_path)
    yield connection
    connection.rollback()
    connection.close()


class Factory:
    """Small insert helpers so each test states only what it is about."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert(self, table: str, **values: object) -> int:
        columns = ", ".join(values)
        params = ", ".join("?" for _ in values)
        cur = self.conn.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({params})",  # noqa: S608 - test helper, fixed names
            tuple(values.values()),
        )
        return int(cur.lastrowid)

    def customer(self, **overrides: object) -> int:
        values = {"full_name": "דנה כהן", "phone": "050-0000000"} | overrides
        return self.insert("customers", **values)

    def address(self, customer_id: int | None, **overrides: object) -> int:
        values = {
            "customer_id": customer_id,
            "street": "הרצל",
            "house_number": "1",
            "city": "תל אביב",
        } | overrides
        return self.insert("addresses", **values)

    def event(self, customer_id: int, **overrides: object) -> int:
        values = {
            "customer_id": customer_id,
            "event_type": "יום הולדת",
            "event_date": "2026-12-20",
            "adults": 20,
        } | overrides
        return self.insert("events", **values)

    def order(self, customer_id: int | None = None, **overrides: object) -> int:
        customer_id = customer_id or self.customer(email=None, phone=f"05{self._n()}")
        event_id = overrides.pop("event_id", None) or self.event(customer_id)
        values = {
            "customer_id": customer_id,
            "event_id": event_id,
            "fulfillment_type": "pickup",
            "requested_at": "2026-12-20T16:00:00Z",
        } | overrides
        return self.insert("orders", **values)

    def priced_order(self, total_minor: int = 150_000, **overrides: object) -> int:
        values = {
            "status": "pending_approval",
            "subtotal_minor": total_minor,
            "delivery_fee_minor": 0,
            "total_minor": total_minor,
            "submitted_at": "2026-11-01T10:00:00Z",
        } | overrides
        return self.order(**values)

    def delivery_order(self, **overrides: object) -> tuple[int, int]:
        customer_id = self.customer(email=None, phone=f"05{self._n()}")
        address_id = self.address(customer_id)
        order_id = self.order(
            customer_id, fulfillment_type="delivery", delivery_address_id=address_id, **overrides
        )
        return order_id, address_id

    def employee(self, **overrides: object) -> int:
        values = {"full_name": "יוסי לוי", "role": "driver"} | overrides
        return self.insert("employees", **values)

    _counter = 0

    def _n(self) -> str:
        Factory._counter += 1
        return f"{Factory._counter:08d}"


@pytest.fixture
def make(conn: sqlite3.Connection) -> Factory:
    return Factory(conn)
