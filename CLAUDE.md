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
uv run python -m scripts.dev_server      # the whole app with a fake login and a demo caterer, no accounts
uv run python -m scripts.migrate         # apply new migrations to DATABASE_URL
uv run uvicorn app.main:app --reload     # http://127.0.0.1:8000  (/health, /admin/, /customer/)
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run pytest tests/test_auth.py::test_garbage_token_is_rejected   # single test
uv run python -m scripts.create_caterer --help                     # onboard a caterer by hand
```

Tests create their own temporary SQLite file, so they need no setup.

E2E tests live in `e2e/` and drive a real browser against the real app and SQLite, with only Supabase Auth and Storage faked. From `backend/`:

```bash
uv run --with playwright playwright install chromium
uv run --with playwright pytest ../e2e
```

The database is SQLite everywhere (ADR 0007). Supabase is used only for Auth and Storage.

Migrations are plain SQL in `database/migrations/` (`YYYYMMDDHHMMSS_name.sql`), run once each in filename order by `apply_migrations`, and in production at container start. New tables are `strict`. There is no ORM autogeneration: `models/` maps a hand-written schema, so a schema change means a new migration plus a model edit.

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

- **One writer at a time.** Non-GET requests hold SQLite's write lock from their first query until they commit (`core/db.py`). Never call the AI, send email, or do other slow work inside a write transaction. GET and HEAD requests are read-only snapshots, so they must not write.
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
| Pilot | First real caterer, needs its own approval | Not started |

Everything up to the Stitch redesign is merged into `dev` and `main` on `origin`. `gh` defaults to `upstream` here, so pass `--repo mardar-anna/ai-catering-platform`.
