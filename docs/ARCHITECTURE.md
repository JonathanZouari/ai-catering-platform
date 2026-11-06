# Architecture

Status: **Draft v0.1** · Phase 0 deliverable

## 1. Overview

```
            Browser (customer / admin)
       HTML + CSS + vanilla JS (fetch → REST,
       supabase-js → Auth, menu, admin, Storage, Realtime)
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
│  repositories/ data access (Postgres)        │
│  models/       table mappings (optional)     │
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
| `repositories/` | One per aggregate; queries against Supabase Postgres | 2 |
| `models/` | Optional SQLAlchemy mappings of the existing tables (the schema itself lives in `supabase/migrations/`) | 2 |
| `schemas/` | Pydantic DTOs and AI tool argument schemas | 2–4 |
| `agents/` | Conversation loop, tool registry, system prompt | 4 |
| `frontend/customer` | Ordering flow + chat panel | 3–4 |
| `frontend/admin` | Owner dashboard | 2 |

## 4. Data access **[RECOMMENDATION]**

Supabase Postgres in every environment (ADR-0002, revised 2026-11-06). No SQLite.

- **Schema:** SQL migrations in `supabase/migrations/` (Supabase CLI), applied to `ai-catering-dev` first, production only after approval. Demo data in `supabase/seed.sql`. Details in `DATABASE_SCHEMA.md`.
- **Backend:** connects directly with `psycopg` (SQLAlchemy 2.x optional, mapped onto the existing tables) using the pooled connection string (`DATABASE_URL`). This privileged connection bypasses RLS and is the only writer for pricing, order submission, the capacity check and AI proposal execution (ADR-0003).
- **Browser:** `supabase-js` (`frontend/js/auth.js`) with the publishable key from `frontend/js/supabase-config.js`, for login, reading the menu, staff admin screens, dish-image upload and Realtime. Row Level Security on every table decides what each request may see or change.
- **Storage:** public bucket `dish-images`. Anyone can view; staff upload, replace and delete straight from the admin page, allowed by storage RLS.
- **Realtime:** `orders` and `order_events`. Staff see every change live, a customer only their own orders.
- **Local development:** the `ai-catering-dev` project, or the local Supabase stack (`supabase start`, needs Docker). Tests run against the local stack.

## 5. Authentication

Supabase Auth (email + password) for staff and customers.

- **Staff:** a login whose user id has an active row in `staff_users`. Pages: `/login/` → `/admin/`.
- **Customer:** a login linked to a `customers` row through `auth_user_id`. Pages: `/login/` → `/account/`. Customers without a login keep using their private order link.
- Roles come from database rows, never from `user_metadata`, which users can edit.
- Still open **[OPEN #1]**: how a new customer signs up and gets linked to an existing customer record (needs phone verification first; see `OPEN_DECISIONS.md`).

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
