# ADR 0005 — SQLite (stdlib) for local persistence

Status: Proposed · Date: 2026-11-02

## Context
ADR-0002 plans Supabase Postgres via SQLAlchemy, which needs a Supabase project and extra dependencies. The customer flow needs real persistence now: a server-owned catalog and orders priced by the backend (ADR-0003).

## Decision
For now the backend uses the stdlib `sqlite3` module with plain SQL migrations in `database/migrations/` (applied idempotently at startup by `app/core/db.py`). The file path comes from `SQLITE_PATH` (default `catering.db`, git-ignored). Money is stored as integer whole shekels; CHECK constraints reject fractional or negative amounts and `total != subtotal + delivery_fee`. This supersedes ADR-0002 until that is revisited; no new dependencies.

## Consequences
+ Zero setup, no extra dependencies, easy to test with a temp file.
− On Railway the file is lost on every redeploy unless a volume is mounted and `SQLITE_PATH` points into it.
− Single writer; not suitable for multiple replicas.
− No row-level security; authorization must live in the services (customer auth is still OPEN #1, so there is no GET order endpoint).
− The schema is simplified compared to `docs/DATABASE_SCHEMA.md` (text ids, no customers/proposals/slots tables) and a later move to Postgres needs a data migration.
