"""Builds a throwaway Postgres database from supabase/migrations, for the tests and E2E.

Used by tests/conftest.py and e2e/server.py, never by the app. The database is wiped, so it
must be a separate database whose name contains "test" (ai_catering_test, not postgres).
Supabase's own auth, storage and realtime pieces are replaced by the small stand-ins below.
"""

from pathlib import Path
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"

# What a Supabase project already has before our migrations run.
SUPABASE_STAND_INS = """
drop publication if exists supabase_realtime;
drop schema if exists public cascade;
drop schema if exists private cascade;
drop schema if exists auth cascade;
drop schema if exists storage cascade;

do $$
begin
    if not exists (select from pg_roles where rolname = 'anon') then
        create role anon nologin;
    end if;
    if not exists (select from pg_roles where rolname = 'authenticated') then
        create role authenticated nologin;
    end if;
end $$;

create schema public;
grant usage on schema public to anon, authenticated;

create schema auth;
grant usage on schema auth to anon, authenticated;
create table auth.users (id uuid primary key, email text);
-- Like Supabase: the user id comes from the request's JWT claims.
create function auth.uid() returns uuid language sql stable as $f$
    select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$f$;
grant execute on function auth.uid() to anon, authenticated;

create schema storage;
create table storage.buckets (
    id text primary key,
    name text not null,
    public boolean not null default false,
    file_size_limit bigint,
    allowed_mime_types text[]
);

create publication supabase_realtime;
"""


def require_test_database(url: str) -> None:
    name = make_url(url).database or ""
    if "test" not in name:
        raise RuntimeError(f"Refusing to wipe database '{name}': its name must contain 'test'")


def reset(engine: Engine) -> None:
    """Drops everything and applies every migration, in filename order."""
    require_test_database(engine.url.render_as_string(hide_password=True))
    with engine.begin() as connection:
        connection.exec_driver_sql(SUPABASE_STAND_INS)
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            connection.exec_driver_sql(migration.read_text(encoding="utf-8"))


def add_auth_user(connection, user_id: UUID) -> None:
    connection.execute(text("insert into auth.users (id) values (:id)"), {"id": user_id})
