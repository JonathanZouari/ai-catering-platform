# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Ordering and quotation web app for a **single catering business** (brand: yumm.ai). Customers plan an event, pick dishes, see backend-calculated quantities and prices, and chat with an AI assistant that can only *propose* changes. The owner approves or rejects every quotation. UI is **Hebrew only, RTL**. Specs live in `docs/` (PRD, ARCHITECTURE, DATABASE_SCHEMA, API_CONTRACTS, AI_AGENT_DESIGN, UX_UI_SPEC, OPEN_DECISIONS, ADR/). Read the relevant one before implementing a feature. `PRODUCT.md` summarizes users, principles and brand constraints.

## Commands

All backend commands run from `backend/` and use [uv](https://docs.astral.sh/uv/):

```bash
cp .env.example .env                      # repo root; config reads .env or ../.env
cd backend
uv sync
uv run uvicorn app.main:app --reload      # http://127.0.0.1:8000  (/health, /customer/, /admin/)
uv run ruff check .                       # lint (rules E,F,I,B,UP,S; line length 100)
uv run ruff format --check .              # format check (CI enforces)
uv run pytest                             # all tests
uv run pytest tests/test_health.py::test_health_ok   # single test
```

The frontend has no build step. Edit the files under `frontend/` and reload the page.

CI (`.github/workflows/ci.yml`) runs `uv sync --frozen`, ruff check, ruff format --check and pytest on pushes and PRs to `dev`/`main`. Commit `uv.lock` changes together with `pyproject.toml` changes.

## Architecture

**One FastAPI service serves both the API and the static frontend.** `backend/app/main.py` mounts `frontend/` at `/` with `StaticFiles(html=True)`. The mount must stay the **last** statement so API routes take precedence. Requests are same-origin, so no CORS is needed. The Dockerfile copies `backend/` and `frontend/` side by side, and `main.py` resolves `frontend/` relative to its own path. Deployment target is Railway (`railway.json`, healthcheck `/health`).

**Backend layering** (`backend/app/`): `api → services → repositories → models`, with `schemas/` (Pydantic DTOs and AI tool args), `agents/` (LLM orchestration) and `core/` (settings via `pydantic-settings`, `get_settings()` is `lru_cache`d). Lower layers never import upper ones. On `main` most of these packages are still empty scaffolds; see the phase plan in `docs/ARCHITECTURE.md`.

**Non-negotiable rules (ADR-0003, AI_AGENT_DESIGN.md):**
- Prices, quantities and order state are computed **only in `services/`**. The frontend and the LLM display or request them, never compute them authoritatively.
- `agents/` calls typed service functions, never the DB. The AI can only create `ai_change_proposals`. A proposal is executed only through a customer HTTP endpoint after the customer approves a visible diff, never by an AI tool.
- Order mutations use optimistic locking (`orders.version`). Proposals are single-use (`executed_at`). Submission freezes a price snapshot on `order_items`.
- A pending quotation must never be presented as a confirmed order. Unknown allergen data (`allergens: null`) is never shown as safe. `[]` means verified none.

**Frontend** (`frontend/`): plain ES modules, no framework.
- `index.html` + `js/landing.js` is the landing page. `customer/` is the 4-step ordering flow. `admin/` is the owner dashboard.
- Customer app: `js/customer/main.js` routes between views (`event → menu → summary → status`). `store.js` holds state (persisted to `localStorage`, bumps `order.version` on every mutation, and subscribers re-render). `views/` and `components/` render into the DOM.
- `js/customer/mock-backend.js` is a **UI-only stand-in** for the API. It mirrors the shapes in `docs/API_CONTRACTS.md` so views can be switched to `js/api.js` (`api()` fetch wrapper, errors shaped `{ error: { code, message, details } }`) without markup changes. Values marked PLACEHOLDER are not business rules.
- Demo shortcut for design review: `/customer/?demo=pending|approved|rejected` (or `#demo-pending`). `?occasion=<type>` preselects the event type.
- Use logical CSS properties (RTL) and respect `prefers-reduced-motion`. Target WCAG 2.2 AA: 44px touch targets, `aria-live` for price totals and chat replies (`js/lib/announce.js`). Visual identity rules are in `docs/VISUAL_IDENTITY.md`. Do not invent photography, logos or testimonials.

## Data / Supabase

Supabase (Postgres, Storage, Auth) is the planned data layer (ADR-0002). On `main`, DB settings in `core/config.py` are optional and `database/migrations/` is empty. The `feat/supabase-foundation` branch adds `supabase/migrations/` (schema, auth, RLS, storage), `supabase/seed.sql`, a login page, a Supabase JS client and RLS tests. Check which branch you are on before assuming the DB exists. The service-role key stays server-side.

## After every completed task

Run these in order and stop at the first failure (fix it, then restart the sequence):

1. **Tests for the change.** Add or update tests that cover what you changed, then run them.
2. **Regression.** Run the full suite plus lint and format from `backend/`: `uv run pytest && uv run ruff check . && uv run ruff format --check .`. For frontend changes, also load the affected page(s) in the running app and check the flow still works.
3. **Security review.** Run `/security-review` on the change. Pay particular attention to auth/RLS, secrets (the service-role key must stay server-side), input validation at API boundaries, and anything that lets the AI mutate orders without customer approval. Fix findings before continuing.
4. **Commit and push.** Commit with a descriptive message and push to the current feature branch. Never push directly to `main`. Work reaches `dev` and `main` through PRs (see below).

## Branches

`main` is production. `dev` is integration. Open feature PRs against `dev` (CI must pass). Releases go `dev` → `main` via PR. Production deploys are manual and need explicit approval.
