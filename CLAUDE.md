# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Ordering/management web app for a single catering business (Hebrew, RTL UI). Customers plan events and get backend-calculated quantities/prices plus an AI assistant; the owner approves every quotation. Specs live in `docs/` (PRD, ARCHITECTURE, API_CONTRACTS, DATABASE_SCHEMA, AI_AGENT_DESIGN, ADRs, OPEN_DECISIONS) — read the relevant one before building a feature. The project is phased (see README); much of the described architecture is not implemented yet.

## Commands

All backend commands run from `backend/` and use [uv](https://docs.astral.sh/uv/):

```bash
cp .env.example .env                       # from repo root; .env is git-ignored
cd backend
uv sync
uv run uvicorn app.main:app --reload       # serves API + frontend at http://127.0.0.1:8000
uv run python scripts/init_db.py           # create/update local SQLite DB (migrations + seed), idempotent
uv run python scripts/create_admin.py owner@example.com   # create/promote owner login in Supabase Auth

uv run ruff check .                        # CI runs: ruff check, ruff format --check, pytest
uv run ruff format --check .
uv run pytest
uv run pytest tests/test_auth.py::test_name   # single test
```

If `uv` is not on PATH (e.g. Git Bash on this Windows machine), use the project venv directly: `backend\.venv\Scripts\python.exe -m pytest` / `-m ruff check .`.

Before committing: run ruff check, ruff format --check and the full pytest suite (existing `test_health.py` / `test_db_schema.py` act as regression tests), then review security-sensitive changes (auth, secrets, anything touching `app_metadata`/keys). `.env` is git-ignored and holds a real `SUPABASE_SECRET_KEY` — never `git add -f` it.

Ruff: line length 100, rules `E F I B UP S` (bandit `S` is on; `assert` allowed only in `tests/`).

## Architecture

- **Single FastAPI monolith serves the static frontend** (`backend/app/main.py`): API routes are registered first, then `frontend/` is mounted at `/` last so API routes win. Same origin, so no CORS. Frontend is plain HTML/CSS/ES modules — no framework, no build step.
- **Intended layering** (`docs/ARCHITECTURE.md`): `api → services → repositories → models`, lower layers never import upper ones. The AI agent (`agents/`) may only call typed service functions, never the DB; mutations go through proposal → approval → execution. Most of these packages are still empty stubs.
- **Backend is authoritative for prices, quantities and order state** (ADR-0003). Frontend and LLM only display/request.
- **Errors** use one shape everywhere: `{"error": {"code", "message", "details"}}`. Raise `ApiError` (`app/core/errors.py`); `frontend/js/api.js` parses this shape.
- **Two databases, deliberately**:
  - Local dev: stdlib `sqlite3`, no ORM (`app/core/db.py`). `init_db` applies `database/migrations/*_sqlite.sql` in order then `database/seed_sqlite.sql`. DB file defaults to `backend/data/yummai.db` (`SQLITE_PATH`).
  - Target/prod: Supabase Postgres (ADR-0002); schema in `supabase/migrations/` (Supabase CLI format, with `supabase/config.toml`). Keep the SQLite and Supabase schemas consistent with `docs/DATABASE_SCHEMA.md` when changing either.
- **Owner auth** (`app/core/auth.py`, `app/api/auth.py`, `frontend/js/admin/auth.js`): browser signs in via Supabase Auth and sends `Authorization: Bearer`; the backend validates by calling Supabase `/auth/v1/user` and requires `app_metadata.role == "admin"` (never `user_metadata`, which users can edit). Public sign-up is disabled; accounts are created only via `scripts/create_admin.py` using the secret key. `GET /api/auth/config` exposes the publishable key to the login page. Use the `require_admin` dependency to protect admin routes.
- **Frontend customer app** (`frontend/js/customer/`): views + components + a small store, currently running against `mock-backend.js`, whose shapes mirror `docs/API_CONTRACTS.md` so views can switch to `api()` calls without markup changes. Mock values marked PLACEHOLDER are not business rules. A dish's `allergens: null` means unknown and must never be displayed as safe (`[]` means verified none).

Known security follow-ups (non-blocking): `frontend/js/admin/auth.js` loads supabase-js from jsDelivr without SRI (pin/vendor it); `create_admin.py --password` leaves the password in shell history and does not enforce its stated minimum length.

## Config

`app/core/config.py` (`pydantic-settings`, reads `.env` or `../.env`): `APP_ENV`, `DATABASE_URL`, `SQLITE_PATH`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` (browser-safe), `SUPABASE_SECRET_KEY` (server-only, never expose). Key names are the new Supabase ones (publishable/secret), not anon/service-role.

## Git workflow

Remotes: `origin` is the user's fork, `upstream` is `JonathanZouari/ai-catering-platform`. Feature work → PR into `dev` (CI must pass); release is a PR `dev` → `main`; production deploys are manual and need explicit approval (ADR-0004). Deployed on Railway via `Dockerfile` (healthcheck `/health`).
