# ADR 0002 — Supabase Postgres in production, SQLite for local development, via SQLAlchemy

Status: Proposed (adopted in Phase 2) · Date: 2026-10-29 · Revised: 2026-11-02 (SQLite for local dev)

## Context
Supabase is mandated for production. Options: supabase-py (PostgREST) or a direct Postgres connection with SQLAlchemy.
Developers and tests also need a database that runs without a Supabase project or a local Postgres server.

## Decision
The backend uses SQLAlchemy 2.x against two engines, chosen by `DATABASE_URL`:

- **Production (and Railway environments):** Supabase Postgres via `psycopg`.
- **Local development and tests:** a SQLite file (`sqlite:///...`).

Supabase client/SDK is used only where needed (Storage). Schema changes are **Alembic** migrations generated from the SQLAlchemy models and applied to both engines (replacing hand-written Supabase CLI SQL). The schema avoids Postgres-only features so it runs unchanged on both; conventions are in `DATABASE_SCHEMA.md`.

Staff (owner) login uses a `staff_users` table with password hashes rather than Supabase Auth, so login behaves the same on both engines.

## Consequences
+ Real transactions and row locks on Postgres (`SELECT … FOR UPDATE`, advisory locks), needed for safe proposal execution and the daily capacity check.
+ Zero-setup local development and fast tests on SQLite.
− Postgres-only types and features (enums, `jsonb`, `numeric`, RLS) are not used. Money is integer agorot.
− SQLite and Postgres differ in locking and type strictness, so integration tests must also run against Postgres before release (CI service container or the Supabase dev project).
− RLS is defense-in-depth only, since the backend connects with a privileged role; authorization is enforced in services.
