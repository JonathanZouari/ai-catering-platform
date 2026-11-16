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
│  repositories/ data access (SQLAlchemy)      │
│  models/       ORM models                    │
│  schemas/      Pydantic request/response/tool│
│  core/         config, logging, security     │
│                                              │
│  static mount: /customer, /admin, /css, /js  │
└──────────────┬──────────────────┬────────────┘
               │                  │
               ▼                  ▼
   Supabase Postgres       Supabase Storage      LLM provider [OPEN]
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
| `repositories/` | One per aggregate; SQLAlchemy sessions | 2 |
| `models/` | SQLAlchemy ORM models matching `DATABASE_SCHEMA.md` | 2 |
| `schemas/` | Pydantic DTOs and AI tool argument schemas | 2–4 |
| `agents/` | Conversation loop, tool registry, system prompt | 4 |
| `frontend/customer` | Ordering flow + chat panel | 3–4 |
| `frontend/admin` | Owner dashboard | 2 |

## 4. Data access **[RECOMMENDATION]**

- Backend connects to Supabase Postgres directly with SQLAlchemy 2.x + `psycopg` using the pooled connection string (`DATABASE_URL`).
- **Current state:** the browser uses supabase-js with the publishable key, served by `GET /api/public-config`. FastAPI has no database connection yet.
- Order submission and owner decisions run in Postgres functions (`submit_order`, `decide_order`), so the database calculates prices and clients cannot write `orders`. Move this logic to `services/` when the backend gets its connection.
- Dish images live in the public `dish-images` bucket. Anyone can read them by URL; only the admin can write.
- Schema changes are SQL migrations in `supabase/migrations/`, applied to dev first.
- RLS is enabled on all tables. It is the primary access control while the browser talks to Supabase directly.
- Realtime publishes `orders` and the catalog and logistics tables. Events respect RLS, so customers only receive their own orders.

## 5. Authentication **[DECIDED 2026-11-05]**

- Supabase Auth with email and password, for both customers and the owner.
- A database trigger creates a `customers` row for each new account.
- The owner is a user with `app_metadata.role = 'admin'`, which only the service role can set. Never authorize from `user_metadata`.

## 6. Environments and branches **[CONFIRMED]** (separate Supabase projects strongly preferred)

| Git branch | Railway environment | Supabase project | Deploys |
|---|---|---|---|
| `dev` | `development` | `ai-catering-dev` | Auto on push to `dev` (after Phase 6 approval) |
| `main` | `production` | `ai-catering-prod` | Manual / explicit approval only |

- Each Railway environment has its own variables (`APP_ENV`, `DATABASE_URL`, `SUPABASE_*`, LLM key).
- Feature work → PR into `dev` → CI must pass → merge. Release → PR `dev` → `main` → CI → merge → manual production deploy.

## 7. CI/CD

GitHub Actions on push/PR to `dev` and `main`: `uv sync` → `ruff check` → `ruff format --check` → `pytest`. Railway handles builds; CI does not deploy.

## 8. Error handling & logging

- Consistent error response shape (`API_CONTRACTS.md`).
- Structured logs without secrets or unnecessary personal data (no addresses/phone numbers in logs).
- Proposal execution in a single DB transaction; failure leaves the order unchanged.

## 9. ADRs

See `docs/ADR/`.
