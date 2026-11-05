"""Parse every MVP migration. Behavioral/security assertions run in mvp-postgres.mjs."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".test-tools"))
from pglast import parse_sql  # noqa: E402

optional = {"employees", "payments", "ingredients", "ingredient_batches", "ingredient_movements",
            "equipment_items", "equipment_movements", "deliveries"}
for path in sorted((ROOT / "migrations").glob("*.sql")):
    sql = path.read_text(encoding="utf-8")
    assert sql.strip(), f"Empty migration: {path.name}"
    parse_sql(sql)
    tables = set(re.findall(r"CREATE TABLE (?:IF NOT EXISTS )?public\.(\w+)", sql, re.I))
    assert not tables & optional, f"Optional tables in MVP: {tables & optional}"
    assert not re.search(r"SECURITY\s+DEFINER", sql, re.I), "Review unexpected privileged function"
    print("PARSED:", path.name)
print("PASS static SQL/scope checks; runtime SQL assertions are separate.")