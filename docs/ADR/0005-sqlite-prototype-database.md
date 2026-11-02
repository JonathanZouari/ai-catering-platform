# ADR 0005 — SQLite for the prototype, production database undecided

Status: Proposed · Date: 2026-11-02 · Amends ADR 0002 (does not supersede it)

## Context
ADR 0002 plans Supabase Postgres via SQLAlchemy. For the prototype we want a database with no external
service, no credentials and no setup. Whether production stays on Supabase or moves to SQLite is **not
decided yet**.

## Decision
- The prototype uses a SQLite file (`data/catering.db`, git-ignored, path set by `DATABASE_PATH`).
- Access is plain stdlib `sqlite3` in `backend/app/core/db.py`. No ORM, so no new dependency.
- Schema changes are numbered SQL files in `database/migrations/`, applied in order by a small runner
  (on app start, or `python -m app.core.db migrate`). Dev placeholder data lives in `database/seeds/`
  and is loaded only on request (`python -m app.core.db seed`).
- ADR 0002 stays in force for production until a later ADR replaces it.

## How SQLite differs from the Postgres draft (`docs/DATABASE_SCHEMA.md`)
| Postgres draft | SQLite prototype |
|---|---|
| `uuid` ids | text ids (random hex default; seed rows use readable ids) |
| `numeric(10,2)` money | **integer agorot**; column names unchanged, so `unit_price = 8500` means ₪85 |
| enums | `CHECK (col IN (...))` |
| `timestamptz`, `jsonb` | ISO-8601 UTC text, JSON text with `json_valid()` checks |
| `SELECT … FOR UPDATE` | `BEGIN IMMEDIATE` (`db.transaction()`) plus the existing `orders.version` check |
| RLS | not applicable; authorization stays in services (as ADR 0002 already assumed) |

## Consequences
+ Zero setup; tests run on in-memory SQLite in under a second.
+ The full draft schema, including its safety rules (unknown ≠ free allergen, price snapshots, one pending
  proposal per order), is enforced by constraints.
− Railway wipes the container disk on redeploy unless a volume is mounted at the DB path. Data loss on
  deploy is acceptable for the prototype only.
− A single writer at a time. Fine for one business; revisit before real traffic.
− Moving to Postgres later means porting the SQL (money as integer agorot can stay) and the `sqlite3` calls.
  Hand-written SQL keeps that cost visible, and no ORM means no abstraction hiding it.
