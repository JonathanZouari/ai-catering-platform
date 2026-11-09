# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Ordering and management web app for a single catering business (brand: yumm.ai). Hebrew-only, right-to-left UI. Customers plan an event, pick dishes, get backend-calculated quantities and prices, and chat with an AI assistant that can only *propose* changes the customer must approve. The owner approves or rejects every quotation. Specs live in `docs/` (PRD, ARCHITECTURE, DATABASE_SCHEMA, API_CONTRACTS, AI_AGENT_DESIGN, UX_UI_SPEC, OPEN_DECISIONS, ADRs). `PRODUCT.md` holds product principles and brand constraints.

Status: early phases. The backend has only `/health` plus the static mount; the customer flow runs on a frontend mock backend; the Supabase schema is real and applied to the dev project.

## Commands

Backend (run from `backend/`, uses [uv](https://docs.astral.sh/uv/)):

```bash
uv sync
uv run uvicorn app.main:app --reload      # http://127.0.0.1:8000 — serves API and frontend
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run pytest tests/test_health.py::test_health_ok   # single test
```

CI (`.github/workflows/ci.yml`) runs exactly `uv sync --frozen`, `ruff check`, `ruff format --check`, `pytest` on pushes/PRs to `dev` and `main`. Ruff: line length 100, rules `E F I B UP S`.

Database (Supabase CLI, repo is linked to project `ai-catering-dev`; CLI password in `SUPABASE_DB_PASSWORD`):

```bash
supabase migration new <name>                       # never edit an applied migration
supabase db push --remote                           # apply new migrations
supabase db query --remote -f supabase/seed.sql     # load synthetic demo data
supabase db query --remote --read-only -f supabase/tests/rls_check.sql   # verify every table has RLS + policies
supabase db advisors --remote                       # security/perf checks before merging
```

Remote writes (`db push`, non-read-only `db query`) change the shared dev database — get explicit user approval first. Test a new migration plus `seed.sql` inside `BEGIN … ROLLBACK` before pushing.

## Architecture

**One FastAPI service** (`backend/app/main.py`) that also serves `frontend/` as static files, mounted last at `/` so API routes win. Same origin, no CORS. Deployed to Railway via the root `Dockerfile` (healthcheck `/health`). Settings come from env via `pydantic-settings` (`app/core/config.py`, reads `.env` or `../.env`).

**Backend layering** (`api → services → repositories → models`, lower layers never import upper ones; `schemas/` = Pydantic DTOs and AI tool argument schemas; `agents/` = LLM orchestration). Most packages are still empty placeholders. Key rules from `docs/ARCHITECTURE.md` and ADR-0003:
- The backend is authoritative for prices, quantities, order state and availability. Frontend and LLM only display or request.
- The AI agent calls typed service functions only, never the database. Mutations go through proposal → customer approval → execution in one transaction.
- Backend DB access will be direct `psycopg` over `DATABASE_URL` (privileged, bypasses RLS). LLM provider is still undecided.

**Supabase** is used in every environment (no SQLite, no portability compromises). Schema is defined only by `supabase/migrations/` (enum types, jsonb, `updated_at` triggers, RLS on every table). `docs/DATABASE_SCHEMA.md` / `docs/ERD.md` describe it and should be kept in sync with migrations. Notables: separate `events` table (one event → many orders, composite FK keeps `order.customer = event.customer`); an order's delivery zone is derived from its city; Realtime on `orders` and `order_events`; public `dish-images` storage bucket with staff-only writes.

**Auth:** Supabase Auth (email+password) for both roles. Staff = active row in `staff_users`; customer = `customers.auth_user_id` matches. Roles come from DB rows, never `user_metadata`. Browser side is `frontend/js/auth.js` (supabase-js from a pinned CDN URL) with the publishable key in `frontend/js/supabase-config.js` — never put the service-role key in the frontend.

**Frontend:** plain HTML/CSS/ES modules, no framework or build step. Pages: `/` (landing), `/customer/`, `/admin/`, `/login/`, `/account/`. The customer app (`frontend/js/customer/`) is a small state machine: `store.js` (state, steps `event → menu → summary → status`, localStorage draft, `order.version` bumped on every mutation), `views/` per step, `components/`. `mock-backend.js` stands in for the API and mirrors the shapes in `docs/API_CONTRACTS.md` so views can later switch to `api()` (`frontend/js/api.js`, errors as `{ error: { code, message, details } }`). Values marked PLACEHOLDER in the mock are not business rules. `?demo=pending|approved|rejected` seeds review states.

## Product constraints that affect code

- A pending quotation must never look like a confirmed order.
- Allergens: `[]` means verified none, `null` means unknown — unknown is never shown as safe.
- WCAG 2.2 AA: 44px touch targets, visible focus, `aria-live` for totals and chat replies, `prefers-reduced-motion` respected, logical CSS properties (RTL).
- Israeli law (IS 5568 / WCAG 2.0 AA, accessibility regulations 2013) requires the accessibility statement at `/accessibility/`. Every page needs a skip link and a link to it (enforced by `backend/tests/test_accessibility.py`; a new page must be added to `PAGES` there). Update the statement's date when it changes. Its coordinator contact fields are still placeholders for the business to fill in. Never invent them.
- No fabricated photos, logos, testimonials or customer data; dish names/prices are mock.

## Branches

`main` = production, `dev` = integration. Feature branches PR into `dev`; releases PR `dev → main`. Production deploys are manual and need explicit approval. Never commit `.env*` (only `.env.example`).

## Testing

After every implementation, run and report the actual results:
- E2E tests on the full user flow
- Regression tests, to confirm existing features still work
- Edge cases (empty, missing, very long or invalid input)

## Security

- After every stage of execution, run a security review: injection, prompt injection, input validation, and secrets or API keys in code
