# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Hebrew (RTL) catering site. Since ADR 0008 it is the site of one caterer, טעם של יחד, served at `/` (the `SITE_CATERER` setting); the multi-caterer code and `/c/{slug}/` links stay. The design follows the Stitch export in `stitch_catering_website_ux_design/` (local, git-ignored); see `docs/UX_UI_SPEC.md`. Customers build an order with a text AI assistant and submit a quote; the caterer approves or rejects it. No payments, no marketplace.

Language rule: UI strings, API error `message`s, and AI replies are Hebrew. Code, API error `code`s, and `docs/` are English. Chat with the user in English.

Specs live in `docs/`: start with `PRD.md`; `OPEN_DECISIONS.md` lists what's undecided. Don't invent answers to open decisions. Build on the listed working default, or ask.

## Commands

Run from `backend/`. Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python -m scripts.dev_server      # the whole app against yummai-dev (keys in ../.env.supabase-dev)
uv run python -m scripts.seed_supabase ../.env.supabase-dev --reset   # rebuild the demo caterer and data
uv run uvicorn app.main:app --reload     # http://127.0.0.1:8000  (/health, /admin/, /customer/)
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run pytest tests/test_auth.py::test_garbage_token_is_rejected   # single test
uv run python -m scripts.create_caterer --help                     # onboard a caterer by hand
```

Tests need a Postgres database whose name contains `test`. They wipe it and rebuild it from `supabase/migrations/` (`scripts/test_database.py`). Locally they read `TEST_DATABASE_URL` and `E2E_DATABASE_URL` from the git-ignored `.env.test`, which points at a portable Postgres 17 in `C:/Users/User/postgres17`, port 54329. If it isn't running, start it with `C:/Users/User/postgres17/pgsql/bin/pg_ctl -D C:/Users/User/postgres17/data -l C:/Users/User/postgres17/server.log start`. CI runs its own Postgres service.

E2E tests live in `e2e/` and drive a real browser against the real app and Postgres, with only Supabase Auth, Storage and Realtime faked. From `backend/`:

```bash
uv run --with playwright playwright install chromium
uv run --with playwright pytest ../e2e
```

The database is Supabase Postgres (ADR 0009). The projects are `yummai-dev` and `yummai-test`, and their keys are in the git-ignored `.env.supabase-dev` and `.env.supabase-test`. Supabase also provides Auth, Storage and Realtime.

Migrations are plain SQL in `supabase/migrations/` (`YYYYMMDDHHMMSS_name.sql`), applied with `supabase db push --remote` (dev first, production only with approval). New tables need RLS and a read policy; `tests/test_rls.py` fails without them. There is no ORM autogeneration: `models/` maps a hand-written schema, so a schema change means a new migration plus a model edit.

## Architecture

One FastAPI app serves the REST API and static `frontend/` (plain HTML/CSS/JS modules, no framework or build step). Layers import downward only: `api → services → repositories → models`. `agents/` (Phase 7) may only call services through typed tools, never the database.

### Tenant isolation (ADR 0005)

This is the most important invariant. Isolation is enforced by the code and the schema together:

- A request's `CatererScope` is built server-side only: from the login (`api/deps.py`), a URL slug, or (Phase 5) the order's private token. Never from a request body or model output.
- Tenant data goes through a `ScopedRepository` subclass (`repositories/base.py`), which requires a scope. `add()` overwrites any `caterer_id` the caller set.
- Input schemas use `extra="forbid"`, so a body naming `caterer_id` is rejected.
- Another caterer's resource returns the same `404` as a missing one, never `403`.
- Referencing tables use composite FKs on `(caterer_id, ...)`, so the database rejects cross-caterer links. New tenant tables need `caterer_id` and these FKs.

`tests/test_tenant_isolation.py` has guards that fail on new `/api/admin` routes without login and new tables without tenant scope. New tables with no `caterer_id` must be added to its explicit allowlists. Add cross-caterer tests for each new resource.

### Other invariants

- **Locks stay short.** Writes that check then change a row take `FOR UPDATE` locks until they commit (`OrderRepository.lock`). Never call the AI, send email, upload, or do other slow work inside such a transaction. GET and HEAD requests run in read-only transactions, so they must not write.
- **The API only reads.** Through the Supabase Data API and Realtime, a caterer can only read its own rows; every write goes through FastAPI. The dashboard's Realtime messages only trigger a reload from our API (`frontend/js/admin/realtime.js`).
- **Backend is authoritative.** Prices, quantities, and order state are computed in `services/`, never by the frontend or the LLM.
- **The AI only proposes.** No agent tool mutates an order; only the customer-facing approve endpoint does (`docs/AI_AGENT_DESIGN.md`, ADR 0003).
- **Unknown stays unknown.** Null dietary fields and missing allergen rows mean unknown, never "no" or "free". Null calories are shown as unknown and are never estimated.
- **Customer links are credentials** (ADR 0006). Tokens live in the URL fragment and the `X-Order-Token` header, are stored hashed, and must stay out of logs. Pages holding a token load no third-party scripts.

### Conventions

- Errors are raised as `AppError` (`core/errors.py`) and render as `{"error": {"code", "message", "details"}}`.
- Sessions don't auto-commit. Services commit explicitly so database errors reach the response.
- Frontend CSS uses logical properties only (`margin-inline-start`, not `margin-left`), since the UI is RTL.
- Fonts and icons are our own files (`frontend/fonts/`, `frontend/img/icons/` via `css/icons.css`); the security policy blocks CDNs.
- The customer page's URL fragment holds the order token, so in-page navigation never uses `#` links.

## Branches

Feature work goes through a PR into `dev`; releases go `dev` → `main`. Production deploys are manual and need explicit approval. `upstream` is a different repository; `origin` is the user's.

## Required workflow

These are mandatory for every phase and feature:

1. **Plan before executing.** Present a plan and get approval before writing code.
2. **Test end to end after writing code.** Run the E2E tests through a real browser, plus the full regression suite (`uv run pytest`, which covers all earlier phases), and report the results.
3. **Run the `security-review` skill** on the changes and fix what it finds before calling the work done.
4. **Document every finished phase in Obsidian**, in the `AI Catering Platform` folder of the vault: what was built, decisions, test results, and known gaps.

## Phases

Worked in order. Don't build features of a later phase early.

| Phase | What | Status |
|---|---|---|
| 0 | Project docs | Done |
| 1 | Project scaffolding | Done |
| 2 | Multi-caterer Hebrew specs | Done |
| 3 | Tenant foundation: schema, caterer login, isolation | Done |
| 4 | Hebrew caterer dashboard | Done |
| 5 | Customer ordering | Done |
| 6 | Quote approval | Done |
| 7 | AI assistant, not yet run against the real model | Done |
| 8 | Ready to go live: rate limits, security headers, Docker, deployment guide | Done |
| Design | Redesign and Yummai logo | Done |
| Emails | New-order email to caterers, not yet tested with the real provider | Done |
| SQLite | Replaced Postgres everywhere (ADR 0007) | Done |
| Test site | Supabase Auth and Storage plus Railway with a volume, needs the user's accounts and approval | Skipped for now |
| Stitch redesign | One caterer's site, Stitch design, homepage video (ADR 0008) | Done |
| Supabase Postgres, part 1 | `yummai-dev` and `yummai-test` projects: schema, read-only RLS, `caterer-assets` bucket, Realtime on `orders`, demo login and synthetic data (`scripts/seed_supabase.py`). The app still runs on SQLite | Done |
| Supabase Postgres, part 2 | The app runs on Supabase Postgres (ADR 0009), tests on local Postgres, live order list in the dashboard | Done |
| Pilot | First real caterer, needs its own approval | Not started |

Everything up to the Stitch redesign is merged into `dev` and `main` on `origin`. `gh` defaults to `upstream` here, so pass `--repo mardar-anna/ai-catering-platform`.
