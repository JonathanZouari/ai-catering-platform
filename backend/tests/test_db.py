import sqlite3

import pytest

from app.db import init_db


def test_schema_and_constraints(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"orders", "order_items", "ai_change_proposals", "dishes"} <= tables
    with pytest.raises(sqlite3.IntegrityError):  # foreign keys enforced
        conn.execute(
            "INSERT INTO events (id, customer_id, event_type, event_date, adults, children) "
            "VALUES ('e', 'nope', 'x', '2026-01-01', 1, 0)"
        )
