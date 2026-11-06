"""Database connection URL and the migration runner (Phase 6)."""

import pytest

from app.core.db import engine_args
from app.core.migrate import MIGRATIONS, migrate
from tests.conftest import PG_URL


def test_supabase_urls_use_psycopg3_without_prepared_statements():
    for given in ("postgres://u:p@h:6543/db", "postgresql://u:p@h:6543/db"):
        assert engine_args(given) == (
            "postgresql+psycopg://u:p@h:6543/db",
            {"prepare_threshold": None},
        )
    assert engine_args("sqlite:///./dev.db") == ("sqlite:///./dev.db", {})


def test_migrations_are_numbered_in_order():
    names = [p.name for p in sorted(MIGRATIONS.glob("*.sql"))]
    assert names and names == sorted(names)
    assert [n[:4] for n in names] == [f"{i:04d}" for i in range(1, len(names) + 1)]


@pytest.mark.skipif(not PG_URL, reason="needs TEST_DATABASE_URL (Postgres)")
def test_migrate_applies_each_file_once(pg_engine):
    assert migrate(PG_URL) == []  # pg_engine already applied everything
    assert migrate(PG_URL, dry_run=True) == []


@pytest.mark.skipif(not PG_URL, reason="needs TEST_DATABASE_URL (Postgres)")
def test_every_table_has_rls_but_not_forced(pg_engine):
    # anon/authenticated (Supabase Data API) see nothing; the owner (the app) is unaffected
    with pg_engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "select relname, relrowsecurity, relforcerowsecurity from pg_class c "
            "join pg_namespace n on n.oid = c.relnamespace "
            "where n.nspname = 'public' and c.relkind = 'r'"
        ).all()
    assert rows
    assert [r[0] for r in rows if not r[1] or r[2]] == []
