# ADR 0009 — Supabase Postgres, with read-only RLS and Realtime

## Status
Accepted (2026-11-05, product owner). Replaces ADR 0007. ADR 0002's Postgres choice is back.

## Context
ADR 0007 put the app on one SQLite file and used Supabase only for Auth and Storage. The product owner then asked for the tables to live in Supabase, with row-level security and Realtime, so that changes show in the dashboard as they happen. Realtime only works on tables stored in Supabase.

The work was split in two. Part 1 created the Supabase side: projects, schema, RLS, the bucket, Realtime and demo data. Part 2 moved the app.

## Decision
- **One Postgres per environment, in Supabase.** The organization is `Yummai`. The projects are `yummai-dev` and `yummai-test`, both in eu-central-1. The app connects with psycopg through the session pooler as a privileged role (`DATABASE_URL`).
- **Migrations live in `supabase/migrations/`.** Deploys apply them with `supabase db push`, and the app no longer migrates at start. A schema change still means a new migration plus a model edit.
- **The backend stays the only writer** (ADR 0003). Through the Data API and Realtime:
  - a logged-in caterer can only *read* its own caterer's rows;
  - `anon` can read only `allergens`;
  - no API role has INSERT, UPDATE or DELETE.

  The caterer comes from `private.current_caterer_id()`. That helper is a security definer with an empty `search_path`, in a schema the API doesn't expose.
- **Locks.** Writes that check and then change a row use `SELECT ... FOR UPDATE` (`OrderRepository.lock`, `lock_slot`). GET and HEAD requests run in read-only transactions, so the database refuses a write.
- **Realtime on `orders` only.** The dashboard uses a small client of our own (`frontend/js/admin/realtime.js`) instead of supabase-js. A message is only a signal: the page reloads the list from our API. RLS makes Supabase send each caterer only its own orders.
- **Tests run on Postgres.** Locally that's a portable Postgres 17; in CI it's a Postgres service. Each test run uses a separate database whose name contains `test` (`scripts/test_database.py`), with small stand-ins for Supabase's `auth`, `storage` and `realtime` pieces. The suite refuses any other database.

What came back from SQLite, and how it's done now:

| SQLite (ADR 0007) | Postgres |
|---|---|
| `BEGIN IMMEDIATE` write lock | `FOR UPDATE` row locks |
| Integer hundredths, UTC text | `numeric(10,2)`, `timestamptz` |
| Text with `CHECK` | Native enum types |
| Migrations at container start | `supabase db push` before a deploy |
| Volume and our own backups | `supabase db dump` copies; managed daily backups need a paid plan |
| No RLS | Read-only RLS on every table, tested in `tests/test_rls.py` |

## Consequences
+ Realtime works, and RLS is a fifth tenant defense again.
+ The database no longer ties the app to one instance; only the in-memory rate limits still do.
+ No volume or file to look after. Managed daily backups are one plan upgrade away; until then, `supabase db dump` copies.
− The database is a network hop away, so slow work must still stay outside transactions that hold row locks.
− Running locally needs either the `yummai-dev` keys or a local Postgres for tests.
− New tables must enable RLS and add a policy. `test_rls.py` fails if they don't.
