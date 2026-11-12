"""Rebuild catering.db from schema.sql + seed.sql. Run: python3 database/sqlite/build_db.py"""

import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE / "catering.db"

DB.unlink(missing_ok=True)
con = sqlite3.connect(DB)
con.executescript((HERE / "schema.sql").read_text() + (HERE / "seed.sql").read_text())
con.commit()

# Self-check: foreign keys hold and the seed totals add up.
assert con.execute("PRAGMA foreign_key_check").fetchall() == []
draft_total = con.execute(
    "SELECT SUM(oi.quantity * d.unit_price) FROM order_items oi "
    "JOIN dishes d ON d.id = oi.dish_id WHERE oi.order_id = 'order-1'"
).fetchone()[0]
assert draft_total == 1196, draft_total
tables = con.execute("SELECT count(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]
con.close()
print(f"Built {DB} with {tables} tables")
