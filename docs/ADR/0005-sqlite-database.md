# ADR 0005 — SQLite as the application database

Status: Accepted · Date: 2026-11-02 · Supersedes: [ADR 0002](0002-supabase-postgres-sqlalchemy.md)

## Context
The course assignment requires a working SQLite database integrated with the Python backend, covering
employees, addresses, deliveries, income receipts and refunds, reusable equipment (tables and serving
utensils) with inventory movements, and raw ingredients with batches, expiry dates, and inventory
movements. This overrides the earlier Supabase Postgres plan for the database. No Postgres code or
migration had been written.

## Decision
- The database is a single SQLite file (`SQLITE_PATH`, default `data/catering.sqlite3`), accessed with
  Python's standard `sqlite3` module. No ORM and no new dependency.
- All connections come from `app.db.connect()`, which turns on `PRAGMA foreign_keys` (SQLite
  defaults it to off on every connection), sets a busy timeout and WAL mode, and checks that foreign
  keys are really on before handing the connection out.
- Schema changes are forward-only SQL files in `database/migrations/NNNN_name.sql`, applied by
  `app.db.migrate()`: each in its own `BEGIN IMMEDIATE` transaction, recorded in `schema_migrations`
  with a SHA-256 checksum. Re-running applies only new files. Edited or unknown migrations stop the run.
- Initialisation runs on app startup (`DB_AUTO_MIGRATE=true`) and on demand with
  `uv run python -m app.db`.
- Integrity lives in the schema: `STRICT` tables, `CHECK` constraints, composite foreign keys for
  cross-table consistency, and triggers for ledger rules (no negative stock, refunds within the
  receipt, append-only ledgers, documented order status transitions).
- Money is `INTEGER` minor units (`*_minor`), converted at the edge with `app.db.money` (Decimal in,
  Decimal out, floats rejected).
- Supabase may still be used for Storage (dish images) and Auth if those decisions stand. It no longer
  holds application data.

## Consequences
+ Zero infrastructure for development, tests, and the course: every test gets a fresh file.
+ The database itself rejects invalid data, so services and the future AI agent cannot bypass the rules.
− One writer at a time. That is fine for a single catering business but not for heavy concurrent writes.
− No row-level locks (`SELECT … FOR UPDATE`). Proposal execution (ADR 0003) uses `BEGIN IMMEDIATE`
  plus the `orders.version` optimistic check instead.
− Hosting needs a persistent volume: the container filesystem on Railway is ephemeral. Backups are a
  file copy taken with `sqlite3 .backup` or the `VACUUM INTO` statement.
− Separate dev/prod data means separate database files per Railway environment, not separate Supabase
  projects.
