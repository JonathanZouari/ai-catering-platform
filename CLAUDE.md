# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Verification after every change

After finishing any task that changes code, before reporting it done:

1. Run the tests for what changed, then the full regression suite (`uv run pytest`, plus `ruff check` and `ruff format --check`) to confirm nothing else broke.
2. Run the `security-review` skill on the pending changes.
3. Report the real results. If a check could not run (for example `uv` is missing), say so instead of calling the work verified.

## Project

Ordering and management web app for a single catering business. Customers plan an event, pick dishes, get backend-calculated quantities and prices, and chat with an AI assistant. The owner approves or rejects every quotation. Specs live in `docs/` (PRD, ARCHITECTURE, DATABASE_SCHEMA, API_CONTRACTS, AI_AGENT_DESIGN, UX_UI_SPEC, OPEN_DECISIONS, ADR/); `PRODUCT.md` summarizes product constraints. Check `docs/OPEN_DECISIONS.md` before assuming an undecided topic (customer auth, LLM provider, quantity formulas, allergen wording).

## Commands

Backend uses [uv](https://docs.astral.sh/uv/); run everything from `backend/`:

```bash
cd backend
uv sync                                     # install deps
uv run uvicorn app.main:app --reload        # serves API + frontend at http://127.0.0.1:8000
uv run ruff check .                         # lint (CI runs this)
uv run ruff format --check .                # format check (CI runs this)
uv run pytest                               # all tests
uv run pytest tests/test_health.py::test_name   # single test
```

Config comes from `.env` at the repo root (copy `.env.example`; git-ignored). CI (`.github/workflows/ci.yml`) runs `uv sync --frozen`, ruff check, ruff format --check, pytest on pushes/PRs to `dev` and `main`.

## Architecture

- **Single FastAPI process serves both API and frontend.** `backend/app/main.py` defines API routes (e.g. `/health`) and mounts `frontend/` as `StaticFiles` at `/` *last*, so API routes take precedence. There is no frontend build step.
- **Backend layering** (`backend/app/`): `api`, `core` (settings via pydantic-settings), `models`, `schemas`, `services`, `repositories`, `agents`. Most are still empty scaffolding; SQLAlchemy/Supabase code is planned for Phase 2.
- **Frontend** is plain HTML/CSS/JS ES modules, Hebrew-only and RTL. Pages: `frontend/index.html` (landing), `customer/`, `admin/`. Asset and CSS references use absolute paths (`/css/...`, `/assets/...`), so opening the HTML via `file://` breaks; it must be served from a web root.
- **`frontend/js/api.js`** is the fetch wrapper; backend errors are expected as `{ error: { code, message, details } }`.
- **The customer UI currently runs on a mock backend** (`frontend/js/customer/mock-backend.js`) with state in `store.js`; real endpoints are meant to replace it per `docs/API_CONTRACTS.md`.

## Product rules that constrain code

- Prices and quantities are computed deterministically by the backend, never by the LLM.
- The AI assistant only *proposes* changes; they apply only after the customer approves a visible diff.
- A pending quotation must never be presented as a confirmed booking.
- Unknown allergen data must never be displayed as safe.

## Branches and environments

`main` = production, `dev` = integration; feature work goes by PR into `dev`, releases by PR `dev` -> `main`. Production deploys are manual. Database lives in Supabase (dev and prod projects); the service-role key is server-side only. SQL migrations go in `database/migrations/` (Supabase CLI format). Hosting is Railway via the root `Dockerfile` (healthcheck `/health`).

## Lint config

Ruff: line length 100, py312, rules `E,F,I,B,UP,S` (bandit `S101` is allowed in `tests/`).
