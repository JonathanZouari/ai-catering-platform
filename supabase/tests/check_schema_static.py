"""SCHEMA-ONLY checks: parse the SQL with pglast and inspect it. No database is contacted.

Passing proves the files parse and contain the required structures, not that they behave.
Behaviour is covered by foundation.sql (run by local-postgres.mjs or live_local_checks.py).

    PYTHONPATH=supabase/.test-tools backend/.venv/Scripts/python.exe supabase/tests/check_schema_static.py
"""

import re
import subprocess
import sys
from pathlib import Path

SUPABASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUPABASE / ".test-tools"))
import pglast  # noqa: E402
from pglast.parser import parse_plpgsql_json  # noqa: E402

MIGRATION = SUPABASE / "migrations" / "20261105103436_catering_postgres_foundation.sql"
TEST_SQL = SUPABASE / "tests" / "foundation.sql"
GENERATOR = SUPABASE / "build_foundation.py"
TABLES = {
    "customers", "employees", "addresses", "events", "orders", "deliveries", "payments",
    "equipment_items", "equipment_movements", "ingredients", "ingredient_batches",
    "ingredient_movements", "dishes", "delivery_zones", "order_items", "order_submissions",
}
VIEWS = {
    "order_payment_summary", "equipment_stock", "equipment_out_by_order",
    "ingredient_batch_stock", "ingredient_stock",
}
LEDGERS = ("payments", "equipment_movements", "ingredient_movements")

failures = []


def check(ok, label):
    print(("ok   " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


def code_only(sql):
    return re.sub(r"--[^\n]*", "", sql).replace("\r\n", "\n")


migration = code_only(MIGRATION.read_text(encoding="utf-8"))
statements = pglast.parse_sql(migration)
kinds = [type(s.stmt).__name__ for s in statements]
sql = re.sub(r"\s+", " ", migration)

check("TransactionStmt" not in kinds, "migration has no BEGIN/COMMIT; the runner owns the transaction")
created = {s.stmt.relation.relname for s in statements if type(s.stmt).__name__ == "CreateStmt"}
check(created == TABLES, "exactly the 16 expected tables are created")
for table in sorted(TABLES):
    check(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in sql, f"RLS enabled: {table}")
    check(f"CREATE POLICY catering_managers ON public.{table} FOR ALL TO authenticated" in sql,
          f"manager policy: {table}")
for view in sorted(VIEWS):
    check(f"CREATE VIEW public.{view} WITH (security_invoker=true)" in sql, f"security_invoker view: {view}")
    check(f"REVOKE ALL ON public.{view} FROM PUBLIC, anon, authenticated" in sql, f"view revoked: {view}")

check("DEFINER" not in sql.upper(), "no SECURITY DEFINER")
check("user_metadata" not in sql, "policies never read user_metadata")
check(not re.search(r"\bGRANT\b[^;]*\bTO\b[^;]*\b(anon|public)\b", sql, re.I), "no grant to anon or PUBLIC")
check("payload TEXT NOT NULL CHECK (payload::jsonb IS NOT NULL)" in sql, "payload is canonical text with a JSON check")
check("Asia/Jerusalem" in sql, "Asia/Jerusalem business dates retained")

functions = re.findall(r"CREATE FUNCTION public\.(\w+)\(\) RETURNS trigger(.*?)\$fn\$(.*?)\$fn\$", migration, re.S)
check(len(functions) >= 20, f"trigger functions found ({len(functions)})")
for name, options, _body in functions:
    check("SECURITY INVOKER" in options and re.search(r"search_path\s*=\s*''", options),
          f"invoker with empty search_path: {name}")
    check(f"REVOKE ALL ON FUNCTION public.{name}() FROM PUBLIC, anon, authenticated" in sql, f"execute revoked: {name}")
parse_plpgsql_json(migration)
check(True, "plpgsql function bodies parse")

locks = re.findall(r"FOR (UPDATE|NO KEY UPDATE|SHARE)\b", " ".join(body for _, _, body in functions))
check("UPDATE" not in locks, "no row lock uses FOR UPDATE")
for table, mode in (("orders", "SHARE"), ("ingredients", "SHARE"), ("payments", "NO KEY UPDATE"),
                    ("equipment_items", "NO KEY UPDATE"), ("ingredient_batches", "NO KEY UPDATE")):
    modes = {m for _, _, body in functions
             for m in re.findall(rf"FROM public\.{table} WHERE [^;]*? FOR (NO KEY UPDATE|SHARE|UPDATE)\b", body)}
    check(modes == {mode}, f"{table} locked only with FOR {mode}")
for ledger in LEDGERS:
    check(f"CREATE TRIGGER {ledger}_no_truncate BEFORE TRUNCATE ON public.{ledger} FOR EACH STATEMENT" in sql,
          f"TRUNCATE guard: {ledger}")

test_sql = code_only(TEST_SQL.read_text(encoding="utf-8"))
test_statements = pglast.parse_sql(test_sql)
parse_plpgsql_json(test_sql)
check(type(test_statements[0].stmt).__name__ == "TransactionStmt", "test opens a transaction first")
check(re.fullmatch(r"(?is).*\brollback\s*;\s*", test_sql) is not None, "test ends in ROLLBACK, nothing after it")
last_do = test_statements[-2].stmt
check(type(last_do).__name__ == "DoStmt" and "PASS" in str(last_do.args[0].arg.sval),
      "PASS is raised only inside the last DO block")
check(test_sql.count("PASS") == 1, "PASS appears exactly once")
check("plpgsql.check_asserts" in test_sql, "test forces plpgsql assertions on")

before = MIGRATION.read_bytes()
result = subprocess.run([sys.executable, str(GENERATOR)], capture_output=True, text=True)
check(result.returncode != 0 and "REFUSED" in result.stderr, "generator refuses to run")
check(MIGRATION.read_bytes() == before, "generator left the migration unchanged")

print("\nSCHEMA-ONLY: no database was contacted; this is not a live test.")
print(f"{len(failures)} failure(s)" if failures else "All schema-only checks passed.")
sys.exit(1 if failures else 0)
