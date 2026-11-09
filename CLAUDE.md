# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Ordering/management web app for a single catering business (Hebrew, RTL, mobile-first). Customers build an order, the backend computes prices/quantities, and an AI assistant *proposes* changes that only apply after explicit customer approval. The owner approves/rejects every quotation. Currently **Phase 1 (scaffolding)**: backend only has `/health`; the customer UI runs entirely on a mock backend.

## Commands

Requires [uv](https://docs.astral.sh/uv/). All backend commands run from `backend/`:

```bash
cp .env.example .env              # repo root; git-ignored
cd backend
uv sync
uv run uvicorn app.main:app --reload   # http://127.0.0.1:8000 (/health, /customer/, /admin/)
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run pytest tests/test_health.py::test_name   # single test
```

CI (`.github/workflows/ci.yml`, on PRs/pushes to `dev` and `main`) runs `uv sync --frozen`, ruff check, ruff format --check, pytest. Ruff: line length 100, rules `E,F,I,B,UP,S` (asserts allowed in tests).

The frontend has no build step or tests; edit files in `frontend/` and reload.

## After completing any change

Before reporting a task done, run from `backend/`: `uv run ruff check .` (its `S` rules are the security check), `uv run ruff format --check .`, and `uv run pytest` (regression). Also confirm no secrets or `.env` files are staged (`git diff --cached --name-only`). Report any failure or skipped check explicitly.

## Architecture

- **Single FastAPI service** serves both the API and the static frontend (`backend/app/main.py` mounts `frontend/` at `/` *last* so API routes win). Same origin, so no CORS. See `docs/ADR/`.
- **Planned backend layering** (empty packages today): `api → services → repositories → models`, with `schemas/` (Pydantic) and `agents/`. Lower layers never import upper ones. The AI agent in `agents/` may only call typed service functions, never the DB; all mutations go through proposal → approval → execution (`docs/AI_AGENT_DESIGN.md`, ADR-0003).
- **Backend is authoritative** for prices, quantities, order state and availability; the frontend and LLM only display or request.
- **Frontend**: vanilla HTML/CSS/ES modules, no framework. Customer app is a 4-step flow (`event → menu → summary → status`) wired in `frontend/js/customer/main.js` with `store.js` (state + step guards) and `views/`. `frontend/js/customer/mock-backend.js` fakes the API using the shapes in `docs/API_CONTRACTS.md` (values marked PLACEHOLDER are not business rules); when the real API exists, swap to `frontend/js/api.js` (error shape `{ error: { code, message, details } }`).
- **Data**: Supabase Postgres + SQLAlchemy planned for Phase 2 (`database/migrations/`, Supabase CLI SQL format). Allergen `null` means unknown and must never be displayed as safe.

## Conventions and gotchas

- Specs live in `docs/` (PRD, ARCHITECTURE, DATABASE_SCHEMA, API_CONTRACTS, AI_AGENT_DESIGN, UX_UI_SPEC, OPEN_DECISIONS); check them and `OPEN_DECISIONS.md` before inventing business rules.
- Branching: feature PRs → `dev` (CI must pass); release PR `dev` → `main`. Production deploys are manual and need explicit approval. Never commit secrets; the Supabase service-role key stays server-side.
- Deploy: Railway via root `Dockerfile` (`railway.json`, healthcheck `/health`); no Railway/Supabase project connected yet.
- Dev-only demo shortcuts in the customer UI: `?demo=pending|approved|rejected` and `?occasion=<event type>`.
