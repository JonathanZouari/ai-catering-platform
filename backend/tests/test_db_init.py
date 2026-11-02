import sqlite3
import threading
from pathlib import Path

import pytest

from app.db import MigrationError, connect, migrate
from app.db.__main__ import main as cli
from app.db.migrations import MIGRATIONS_DIR, discover

EXPECTED_TABLES = {
    "schema_migrations",
    "customers",
    "employees",
    "addresses",
    "events",
    "orders",
    "deliveries",
    "payments",
    "equipment_items",
    "equipment_movements",
    "ingredients",
    "ingredient_batches",
    "ingredient_movements",
}
EXPECTED_VIEWS = {
    "order_payment_summary",
    "equipment_stock",
    "equipment_out_by_order",
    "ingredient_batch_stock",
    "ingredient_stock",
}


def _objects(conn: sqlite3.Connection, kind: str) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = ? AND name NOT LIKE 'sqlite_%'", (kind,)
    )
    return {r[0] for r in rows}


def test_fresh_init_creates_schema(isolated_settings: Path):
    assert migrate(isolated_settings) == ["0001"]
    conn = connect(isolated_settings)
    try:
        assert _objects(conn, "table") == EXPECTED_TABLES
        assert _objects(conn, "view") == EXPECTED_VIEWS
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        # Every domain table is STRICT.
        strict = {r["name"] for r in conn.execute("PRAGMA table_list") if r["strict"]}
        assert EXPECTED_TABLES <= strict
    finally:
        conn.close()


def test_rerun_is_noop_and_keeps_data(db_path: Path):
    conn = connect(db_path)
    conn.execute("INSERT INTO customers (full_name, email) VALUES ('Keep Me', 'keep@example.com')")
    conn.commit()
    conn.close()

    assert migrate(db_path) == []
    assert migrate(db_path) == []

    conn = connect(db_path)
    try:
        assert conn.execute("SELECT full_name FROM customers").fetchall()[0][0] == "Keep Me"
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 1
    finally:
        conn.close()


def test_every_connection_enforces_foreign_keys(db_path: Path):
    for _ in range(3):
        conn = connect(db_path)
        try:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
                conn.execute(
                    "INSERT INTO addresses (customer_id, street, city) VALUES (999, 'x', 'y')"
                )
        finally:
            conn.close()


def test_connection_uses_real_transactions(db_path: Path):
    conn = connect(db_path)
    conn.execute("INSERT INTO customers (full_name, phone) VALUES ('Temp', '1')")
    conn.rollback()
    assert conn.execute("SELECT count(*) FROM customers").fetchone()[0] == 0
    conn.close()


def _copy_migrations(tmp_path: Path) -> Path:
    target = tmp_path / "migrations"
    target.mkdir()
    for m in discover(MIGRATIONS_DIR):
        (target / f"{m.version}_{m.name}.sql").write_text(m.sql, encoding="utf-8")
    return target


def test_edited_migration_is_refused(tmp_path: Path, db_path: Path):
    migrations = _copy_migrations(tmp_path)
    path = migrations / "0001_initial_schema.sql"
    path.write_text(path.read_text(encoding="utf-8") + "\n-- edited\n", encoding="utf-8")
    with pytest.raises(MigrationError, match="edited after it was applied"):
        migrate(db_path, migrations)


def test_crlf_checkout_has_same_checksum(tmp_path: Path, db_path: Path):
    migrations = _copy_migrations(tmp_path)
    path = migrations / "0001_initial_schema.sql"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert migrate(db_path, migrations) == []


def test_unknown_applied_version_is_refused(tmp_path: Path, db_path: Path):
    migrations = _copy_migrations(tmp_path)
    (migrations / "0002_extra.sql").write_text("CREATE TABLE extra (id INTEGER PRIMARY KEY);")
    assert migrate(db_path, migrations) == ["0002"]
    with pytest.raises(MigrationError, match="does not know about: 0002"):
        migrate(db_path)  # older code, newer database


def test_failed_migration_rolls_back_completely(tmp_path: Path, db_path: Path):
    migrations = _copy_migrations(tmp_path)
    (migrations / "0002_broken.sql").write_text(
        "CREATE TABLE half_done (id INTEGER PRIMARY KEY);\nINSERT INTO no_such_table VALUES (1);\n"
    )
    with pytest.raises(MigrationError):
        migrate(db_path, migrations)
    conn = connect(db_path)
    try:
        assert "half_done" not in _objects(conn, "table")
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations")]
        assert versions == ["0001"]
    finally:
        conn.close()


def test_migration_with_transaction_control_is_refused(tmp_path: Path, db_path: Path):
    migrations = _copy_migrations(tmp_path)
    (migrations / "0002_commits.sql").write_text("CREATE TABLE t (id INTEGER PRIMARY KEY); COMMIT;")
    with pytest.raises(MigrationError, match="ended the transaction"):
        migrate(db_path, migrations)


def test_bad_migration_filename_is_refused(tmp_path: Path):
    migrations = _copy_migrations(tmp_path)
    (migrations / "add-stuff.sql").write_text("SELECT 1;")
    with pytest.raises(MigrationError, match="0001_name.sql"):
        discover(migrations)


def test_concurrent_initialisation_applies_once(isolated_settings: Path):
    results: list[list[str]] = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            results.append(migrate(isolated_settings))
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert sorted(results) == [[], [], [], ["0001"]]


def test_cli_migrate_and_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    target = tmp_path / "cli" / "db.sqlite3"
    assert cli(["status", "--path", str(target)]) == 0
    assert "pending  0001_initial_schema" in capsys.readouterr().out
    assert not target.exists()  # status never creates a database

    assert cli(["--path", str(target)]) == 0
    assert "applied 0001" in capsys.readouterr().out
    assert cli(["--path", str(target)]) == 0
    assert "up to date" in capsys.readouterr().out
    assert cli(["status", "--path", str(target)]) == 0
    assert "applied  0001_initial_schema" in capsys.readouterr().out
