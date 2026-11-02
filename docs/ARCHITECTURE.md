# Architecture

Status: **Draft v0.1** · Phase 0 deliverable

## 1. Overview

```
            Browser (customer / admin)
       HTML + CSS + vanilla JS (fetch → REST)
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ FastAPI application (one Railway service)    │
│                                              │
│  api/          HTTP routers, auth deps       │
│   │                                          │
│  services/     business rules (pricing,      │
│   │            quantities, order workflow,   │
│   │            proposal validation/execution)│
│   │      ▲                                   │
│   │      │ typed calls only                  │
│   │  agents/   LLM orchestration + tool defs │
│   ▼                                          │
│  repositories/ data access (sqlite3, SQL)    │
│  db/           connections, migrations, money│
│  schemas/      Pydantic request/response/tool│
│  core/         config, logging, security     │
│                                              │
│  static mount: /customer, /admin, /css, /js  │
└──────────────┬──────────────────┬────────────┘
               │                  │
               ▼                  ▼
   SQLite file             Supabase Storage      LLM provider [OPEN]
   (source of truth)       (dish images)
```

## 2. Key principles

1. **Backend is authoritative.** Prices, quantities, order state, and availability are computed and stored by backend code. The frontend and the LLM only display or request.
2. **The AI agent is a client of services, never of the database.** `agents/` may only call service functions exposed as typed tools. Every tool argument is validated by a Pydantic schema. Mutations go through the proposal → approval → execution workflow (`AI_AGENT_DESIGN.md`).
3. **Layered, modular monolith.** `api → services → repositories → models`. Lower layers never import upper layers. Simple to deploy as one Railway service; can be split later if needed.
4. **No frontend framework.** Plain HTML/CSS/JS modules served as static files by FastAPI (same origin → no CORS setup needed). **[CONFIRMED]**
5. **Configuration via environment variables** (`pydantic-settings`). No secrets in Git.

## 3. Components

| Layer | Responsibility | Phase |
|---|---|---|
| `core/config.py` | Typed settings from env | 1 |
| `api/` | Routers: `health`, `catalog`, `orders`, `proposals`, `admin/*` | 1 (health) → 2–4 |
| `services/` | `pricing`, `quantities`, `orders`, `proposals`, `catalog`, `availability`, `delivery` | 2–4 |
| `db/` | `connect()` (foreign keys on), forward-only migration runner, money/timestamp helpers | 2 (done) |
| `repositories/` | One per aggregate; plain SQL over a `sqlite3` connection (`finance`, `inventory` done) | 2 |
| `models/` | Typed row dataclasses where useful. No ORM (ADR 0005) | 2 |
| `schemas/` | Pydantic DTOs and AI tool argument schemas | 2–4 |
| `agents/` | Conversation loop, tool registry, system prompt | 4 |
| `frontend/customer` | Ordering flow + chat panel | 3–4 |
| `frontend/admin` | Owner dashboard | 2 |

## 4. Data access **[RECOMMENDATION]**

**[CONFIRMED]** SQLite, per [ADR 0005](ADR/0005-sqlite-database.md), which supersedes the Supabase Postgres plan.

- Backend uses the standard-library `sqlite3` module. One connection per request via the `get_db` dependency (commit on success, rollback on error). Every connection comes from `app.db.connect()`, which turns on and verifies `PRAGMA foreign_keys`.
- Database file: `SQLITE_PATH` (default `data/catering.sqlite3`, git-ignored). On Railway it must be on a mounted volume.
- Schema changes: forward-only SQL migrations in `database/migrations/NNNN_name.sql`, applied on startup and by `uv run python -m app.db`. Non-destructive and checksummed. See `DATABASE_SCHEMA.md`.
- Integrity rules live in the schema (STRICT tables, CHECKs, composite FKs, triggers), so no caller can bypass them, including the AI agent.
- Authorization is enforced in services. There is no RLS in SQLite.
- Supabase Storage (optional) may still hold dish images, accessed server-side only.

## 5. Authentication **[OPEN]**

- Admin: one owner account. Recommended: Supabase Auth email login, backend verifies the JWT and checks an `admin` role.
- Customer: undecided (account vs guest link). Backend dependencies will be written so either option plugs in.

## 6. Environments and branches **[CONFIRMED]**

| Git branch | Railway environment | Database | Deploys |
|---|---|---|---|
| `dev` | `development` | SQLite file on the dev volume | Auto on push to `dev` (after Phase 6 approval) |
| `main` | `production` | SQLite file on the prod volume | Manual / explicit approval only |

- Each Railway environment has its own variables (`APP_ENV`, `SQLITE_PATH`, `DB_AUTO_MIGRATE`, optional `SUPABASE_*` for Storage, LLM key).
- Feature work → PR into `dev` → CI must pass → merge. Release → PR `dev` → `main` → CI → merge → manual production deploy.

## 7. CI/CD

GitHub Actions on push/PR to `dev` and `main`: `uv sync` → `ruff check` → `ruff format --check` → `pytest`. Railway handles builds; CI does not deploy.

## 8. Error handling & logging

- Consistent error response shape (`API_CONTRACTS.md`).
- Structured logs without secrets or unnecessary personal data (no addresses/phone numbers in logs).
- Proposal execution in a single DB transaction (`BEGIN IMMEDIATE` + `orders.version` check); failure leaves the order unchanged.

## 9. ADRs

See `docs/ADR/`.
