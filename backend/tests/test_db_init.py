import sqlite3
import threading
from pathlib import Path

import pytest

from app.db import MigrationError, connect, migrate
from app.db.__main__ import main as cli
from app.db.migrations import MIGRATIONS_DIR, applied_versions, discover

EXPECTED_VERSIONS = [m.version for m in discover()]

EXPECTED_TABLES = {
    "dish_categories",
    "dish_dietary",
    "allergens",
    "dish_allergens",
    "legacy_catalog_snapshot",
    "dishes",
    "delivery_zones",
    "order_items",
    "order_submissions",
    "schema_migrations",
    "customers",
    "addresses",
    "events",
    "orders",
}
EXPECTED_VIEWS = set()


def _objects(conn: sqlite3.Connection, kind: str) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = ? AND name NOT LIKE 'sqlite_%'", (kind,)
    )
    return {r[0] for r in rows}


def test_fresh_init_creates_schema(isolated_settings: Path):
    assert migrate(isolated_settings) == EXPECTED_VERSIONS
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
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == len(
            EXPECTED_VERSIONS
        )
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
        (target / f"{m.version}_{m.name}.sql").write_text(m.sql, encoding="utf-8", newline="\n")
    return target


def test_edited_migration_is_refused(tmp_path: Path, db_path: Path):
    migrations = _copy_migrations(tmp_path)
    path = migrations / "0004_mvp_baseline.sql"
    path.write_text(path.read_text(encoding="utf-8") + "\n-- edited\n", encoding="utf-8")
    with pytest.raises(MigrationError, match="edited after it was applied"):
        migrate(db_path, migrations)


def test_crlf_checkout_has_same_checksum(tmp_path: Path, db_path: Path):
    migrations = _copy_migrations(tmp_path)
    path = migrations / "0004_mvp_baseline.sql"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert migrate(db_path, migrations) == []


def test_unknown_applied_version_is_refused(tmp_path: Path, db_path: Path):
    migrations = _copy_migrations(tmp_path)
    (migrations / "9999_extra.sql").write_text("CREATE TABLE extra (id INTEGER PRIMARY KEY);")
    assert migrate(db_path, migrations) == ["9999"]
    with pytest.raises(MigrationError, match="does not know about: 9999"):
        migrate(db_path)  # older code, newer database


def test_failed_migration_rolls_back_completely(tmp_path: Path, db_path: Path):
    migrations = _copy_migrations(tmp_path)
    (migrations / "9999_broken.sql").write_text(
        "CREATE TABLE half_done (id INTEGER PRIMARY KEY);\nINSERT INTO no_such_table VALUES (1);\n"
    )
    with pytest.raises(MigrationError):
        migrate(db_path, migrations)
    conn = connect(db_path)
    try:
        assert "half_done" not in _objects(conn, "table")
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations")]
        assert versions == EXPECTED_VERSIONS
    finally:
        conn.close()


@pytest.mark.parametrize("statement", ["COMMIT", "END", "ROLLBACK", "PRAGMA foreign_keys=OFF"])
def test_migration_with_transaction_control_is_refused(tmp_path: Path, db_path: Path, statement):
    migrations = _copy_migrations(tmp_path)
    (migrations / "9999_commits.sql").write_text(
        f"CREATE TABLE t (id INTEGER PRIMARY KEY); {statement};"
    )
    with pytest.raises(MigrationError, match="forbidden transaction control"):
        migrate(db_path, migrations)
    conn = connect(db_path)
    try:
        assert "t" not in _objects(conn, "table")
        assert [
            r[0] for r in conn.execute("SELECT version FROM schema_migrations")
        ] == EXPECTED_VERSIONS
    finally:
        conn.close()


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
    # Each migration owns its transaction; different starters may apply different
    # versions. The invariant is that every version is applied exactly once.
    assert sorted(version for result in results for version in result) == EXPECTED_VERSIONS
    conn = connect(isolated_settings)
    try:
        assert applied_versions(conn) == EXPECTED_VERSIONS
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def test_cli_migrate_and_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    target = tmp_path / "cli" / "db.sqlite3"
    assert cli(["status", "--path", str(target)]) == 0
    assert "pending  0004_mvp_baseline" in capsys.readouterr().out
    assert not target.exists()  # status never creates a database

    assert cli(["--path", str(target)]) == 0
    assert "applied 0004" in capsys.readouterr().out
    assert cli(["--path", str(target)]) == 0
    assert "up to date" in capsys.readouterr().out
    assert cli(["status", "--path", str(target)]) == 0
    assert "applied  0004_mvp_baseline" in capsys.readouterr().out


def test_legacy_course_database_keeps_rows_and_exact_history(tmp_path):
    from app.db.migrations import LEGACY_CHECKSUMS

    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    (baseline_dir / "0004_mvp_baseline.sql").write_bytes(
        (MIGRATIONS_DIR / "0004_mvp_baseline.sql").read_bytes()
    )
    db_path = tmp_path / "legacy.sqlite3"
    migrate(db_path, baseline_dir)
    conn = connect(db_path)
    conn.execute("INSERT INTO customers(full_name,phone) VALUES ('Historical customer','1')")
    conn.execute("CREATE TABLE optional_old_data(id INTEGER PRIMARY KEY, note TEXT) STRICT")
    conn.execute("INSERT INTO optional_old_data VALUES (1,'preserve')")
    conn.execute("DELETE FROM schema_migrations")
    for version, checksum in LEGACY_CHECKSUMS.items():
        conn.execute(
            "INSERT INTO schema_migrations(version,name,checksum) VALUES (?,?,?)",
            (version, "legacy", checksum),
        )
    conn.commit()
    conn.close()
    assert migrate(db_path) == EXPECTED_VERSIONS
    assert migrate(db_path) == []
    with connect(db_path) as conn:
        assert (
            conn.execute("SELECT full_name FROM customers").fetchone()[0] == "Historical customer"
        )
        assert conn.execute("SELECT note FROM optional_old_data").fetchone()[0] == "preserve"
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 3 + len(
            EXPECTED_VERSIONS
        )


def test_unrecognized_legacy_checksum_is_refused(db_path):
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO schema_migrations(version,name,checksum) VALUES ('0001','legacy','bad')"
        )
    with pytest.raises(MigrationError, match="unrecognized checksum"):
        migrate(db_path)
