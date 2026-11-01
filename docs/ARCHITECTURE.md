# Architecture

Status: **Draft v0.2** · Updated in Phase 2 for many caterers

## 1. Overview

```
            Browser (customer / caterer)
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
│  static mount: /c/{slug}, /admin, /css, /js  │
└──────────────┬──────────────────┬────────────┘
               │                  │
               ▼                  ▼
   Supabase Postgres       Supabase Storage      LLM provider (Claude)
   (source of truth)       (dish images, logos)
```

## 2. Key principles

1. **Backend is authoritative.** Prices, quantities, order state, and availability are computed and stored by backend code. The frontend and the LLM only display or request.
2. **The AI agent is a client of services, never of the database.** `agents/` may only call service functions exposed as typed tools. Every tool argument is validated by a Pydantic schema. Mutations go through the proposal → approval → execution workflow (`AI_AGENT_DESIGN.md`).
3. **Layered, modular monolith.** `api → services → repositories → models`. Lower layers never import upper layers. Simple to deploy as one Railway service; can be split later if needed.
4. **No frontend framework.** Plain HTML/CSS/JS modules served as static files by FastAPI (same origin → no CORS setup needed). **[CONFIRMED]**
5. **Configuration via environment variables** (`pydantic-settings`). No secrets in Git.
6. **Every request runs in one caterer's scope.** The caterer is resolved server-side, never taken from a client-supplied ID in the body, and passed explicitly to services and repositories. See section 5 and ADR 0005.
7. **Hebrew-first frontend.** All UI text is Hebrew with `dir="rtl"`. CSS uses logical properties only.

## 3. Components

| Layer | Responsibility | Phase |
|---|---|---|
| `core/config.py` | Typed settings from env | 1 |
| `api/` | Routers: `health`, `catalog`, `orders`, `proposals`, `admin/*` | 1 (health) → 3–7 |
| `services/` | `pricing`, `quantities`, `kashrut`, `orders`, `proposals`, `catalog`, `availability`, `delivery`, `caterers` | 3–7 |
| `repositories/` | One per aggregate; SQLAlchemy sessions; every query takes a caterer scope | 3 |
| `models/` | SQLAlchemy ORM models matching `DATABASE_SCHEMA.md` | 3 |
| `schemas/` | Pydantic DTOs and AI tool argument schemas | 3–7 |
| `agents/` | Conversation loop, tool registry, system prompt | 7 |
| `frontend/customer` | Ordering flow + chat panel | 5–7 |
| `frontend/admin` | Caterer dashboard | 4–6 |
| Internal script | Create a caterer and its first user by hand | 3 |

## 4. Data access **[RECOMMENDATION]**

- Backend connects to Supabase Postgres directly with SQLAlchemy 2.x + `psycopg` using the pooled connection string (`DATABASE_URL`).
- Supabase Storage accessed server-side with the service-role key, only from the backend, for image upload. Object paths are prefixed by caterer ID. Public read for dish images and logos via a public bucket.
- Schema changes as SQL migrations in `database/migrations/` (Supabase CLI format), applied to dev first.
- RLS: enabled on all tables with no anonymous access. The backend uses a privileged connection, so RLS is defense-in-depth and **tenant isolation is enforced in the backend** (ADR 0005).

## 5. Authentication and caterer scope **[CONFIRMED]**

| Actor | Identified by | Caterer scope comes from |
|---|---|---|
| Caterer user | Supabase Auth login; backend verifies the JWT | `caterer_users` membership lookup |
| Customer | Private order link token (ADR 0006) | The order the token belongs to |
| Public catalog visitor | Nobody; read-only | The `{slug}` in the URL |
| Platform operator | Internal script with server access | Explicit argument; no HTTP surface |

A resource from another caterer returns `404`, not `403`, so its existence isn't revealed.

## 6. Environments and branches **[CONFIRMED]** (separate Supabase projects strongly preferred)

| Git branch | Railway environment | Supabase project | Deploys |
|---|---|---|---|
| `dev` | `development` | `ai-catering-dev` | Auto on push to `dev` (after Phase 8 approval) |
| `main` | `production` | `ai-catering-prod` | Manual / explicit approval only |

- Each Railway environment has its own variables (`APP_ENV`, `DATABASE_URL`, `SUPABASE_*`, LLM key).
- Feature work → PR into `dev` → CI must pass → merge. Release → PR `dev` → `main` → CI → merge → manual production deploy.

## 7. CI/CD

GitHub Actions on push/PR to `dev` and `main`: `uv sync` → `ruff check` → `ruff format --check` → `pytest`. Railway handles builds; CI does not deploy.

## 8. Error handling & logging

- Consistent error response shape (`API_CONTRACTS.md`).
- Structured logs include `caterer_id`, without secrets or unnecessary personal data (no addresses, phone numbers, or private link tokens in logs).
- Proposal execution in a single DB transaction; failure leaves the order unchanged.

## 9. ADRs

See `docs/ADR/`.
