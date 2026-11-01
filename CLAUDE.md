# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Hebrew (RTL) catering platform for many caterers. Each caterer has a branded customer link at `/c/{slug}/`. Customers build an order with a text AI assistant and submit a quote; the caterer approves or rejects it. No payments, no marketplace.

Language rule: UI strings, API error `message`s, and AI replies are Hebrew. Code, API error `code`s, and `docs/` are English. Chat with the user in English.

Specs live in `docs/`: start with `PRD.md`; `OPEN_DECISIONS.md` lists what's undecided. Don't invent answers to open decisions. Build on the listed working default, or ask.

## Commands

Run from `backend/`. Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn app.main:app --reload     # http://127.0.0.1:8000  (/health, /admin/, /customer/)
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run pytest tests/test_auth.py::test_garbage_token_is_rejected   # single test
uv run python -m scripts.create_caterer --help                     # onboard a caterer by hand
```

Database tests need `TEST_DATABASE_URL` pointing at a disposable Postgres whose database name contains `test`. **The suite drops the `public` schema of that database**, so never point it at Supabase. Without the variable, database tests skip locally and fail in CI (`CI` set).

E2E tests live in `e2e/` and drive a real browser against the real app and Postgres, with only Supabase Auth and Storage faked. From `backend/`, with `E2E_DATABASE_URL` set to a disposable Postgres whose name contains `test`:

```bash
uv run --with playwright playwright install chromium
uv run --with playwright pytest ../e2e
```

Tests must use real Postgres, not SQLite: composite foreign keys, enums, and RLS are part of what's tested. If there's no Docker or Postgres on the machine, `pip install pgserver` in a throwaway venv gives an embedded Postgres.

Migrations are plain SQL in `database/migrations/` (Supabase CLI naming, `YYYYMMDDHHMMSS_name.sql`). The test fixture applies them in filename order on a stub `auth.users`. There is no ORM autogeneration: `models/` maps a hand-written schema, so a schema change means a new migration plus a model edit.

## Architecture

One FastAPI app serves the REST API and static `frontend/` (plain HTML/CSS/JS modules, no framework or build step). Layers import downward only: `api → services → repositories → models`. `agents/` (Phase 7) may only call services through typed tools, never the database.

### Tenant isolation (ADR 0005)

This is the most important invariant. The backend connects as a privileged role, so RLS doesn't protect it; isolation is enforced by the code and the schema together:

- A request's `CatererScope` is built server-side only: from the login (`api/deps.py`), a URL slug, or (Phase 5) the order's private token. Never from a request body or model output.
- Tenant data goes through a `ScopedRepository` subclass (`repositories/base.py`), which requires a scope. `add()` overwrites any `caterer_id` the caller set.
- Input schemas use `extra="forbid"`, so a body naming `caterer_id` is rejected.
- Another caterer's resource returns the same `404` as a missing one, never `403`.
- Referencing tables use composite FKs on `(caterer_id, ...)`, so the database rejects cross-caterer links. New tenant tables need `caterer_id`, these FKs, and `enable row level security`.

`tests/test_tenant_isolation.py` has guards that fail on new `/api/admin` routes without login and new tables without tenant scope or RLS. New tables with no `caterer_id` must be added to its explicit allowlists. Add cross-caterer tests for each new resource.

### Other invariants

- **Backend is authoritative.** Prices, quantities, and order state are computed in `services/`, never by the frontend or the LLM.
- **The AI only proposes.** No agent tool mutates an order; only the customer-facing approve endpoint does (`docs/AI_AGENT_DESIGN.md`, ADR 0003).
- **Unknown stays unknown.** Null dietary fields and missing allergen rows mean unknown, never "no" or "free". Null calories are shown as unknown and are never estimated.
- **Customer links are credentials** (ADR 0006). Tokens live in the URL fragment and the `X-Order-Token` header, are stored hashed, and must stay out of logs. Pages holding a token load no third-party scripts.

### Conventions

- Errors are raised as `AppError` (`core/errors.py`) and render as `{"error": {"code", "message", "details"}}`.
- Sessions don't auto-commit. Services commit explicitly so database errors reach the response.
- Frontend CSS uses logical properties only (`margin-inline-start`, not `margin-left`), since the UI is RTL.

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
| Test site | Supabase and Railway, needs the user's accounts and approval | Skipped for now |
| Pilot | First real caterer, needs its own approval | Not started |

The code is on `feat/phase-8-deploy-pilot`. PR #1 into `dev` on `origin` is open with CI passing. `gh` defaults to `upstream` here, so pass `--repo mardar-anna/ai-catering-platform`.
