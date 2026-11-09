# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Catering ordering and management web app for a single business. A customer builds an event order, and an AI assistant can propose changes to it; the business owner approves or rejects every quotation. The project is in early phases (see the README status line). Specs live in `docs/`: PRD, ARCHITECTURE, DATABASE_SCHEMA, API_CONTRACTS, AI_AGENT_DESIGN, UX_UI_SPEC, ADRs and OPEN_DECISIONS. Read the relevant spec before building a feature. Items marked `[OPEN]` there are undecided; ask instead of guessing.

## Commands

All backend commands run from `backend/` with [uv](https://docs.astral.sh/uv/):

```bash
uv sync                                   # install deps
uv run uvicorn app.main:app --reload      # dev server: /health, /customer/, /admin/, / (landing)
uv run ruff check .                       # lint (CI)
uv run ruff format --check .              # format check (CI)
uv run pytest                             # all tests
uv run pytest tests/test_health.py::test_health_ok   # single test
```

CI (`.github/workflows/ci.yml`) runs `uv sync --frozen`, both ruff checks and pytest on pushes and PRs to `dev` and `main`. Ruff enforces line length 100 and the rule sets `E,F,I,B,UP,S` (bandit; `S101` is allowed in tests).

The frontend has no build step. Edit the files and reload the page.

## Architecture

- **One FastAPI service** (`backend/app/main.py`) serves the API and mounts `frontend/` as static files at `/`. The mount comes last so API routes win, and every new router must be included *before* it. Because frontend and API share an origin, there is no CORS setup.
- **Layering**: `api → services → repositories → models`, with `schemas/` for Pydantic DTOs and AI tool arguments and `core/` for config. Lower layers never import upper ones. Most of these packages are still empty placeholders, so follow `docs/ARCHITECTURE.md` when filling them.
- **The backend is authoritative (ADR-0003).** Prices, quantities and order state are computed only in `services/`. The AI agent (`agents/`) calls typed service tools and never the DB. It can only *create proposals*. A proposal is applied through a customer-only endpoint, transactionally, with optimistic locking on `orders.version`, and each proposal is single-use.
- **Config**: `core/config.py` uses `pydantic-settings`, which reads `.env` or `../.env`. Get settings through the cached `get_settings()`. Template: `.env.example`.
- **Frontend**: plain ES modules, Hebrew, RTL (`lang="he" dir="rtl"`), mobile-first.
  - `frontend/js/customer/`: `main.js` routes the steps (`event → menu → summary → status`), and `store.js` is a pub/sub state store persisted to localStorage.
  - Views call `mock-backend.js`, which mirrors the shapes in `docs/API_CONTRACTS.md`. Its values marked PLACEHOLDER are not business rules. Later, views switch to `js/api.js` (a fetch wrapper; errors come back as `{ error: { code, message, details } }`).
  - `js/lib/` holds the shared helpers: the `h()` DOM builder, formatters, motion and illustrations. Reuse them.
  - Dev shortcuts: `?demo=pending|approved|rejected` seeds a demo state, and `?occasion=<type>` preselects the event type.
- Allergen data: `null` means unknown and must never be displayed as safe. `[]` means verified to have no allergens.

## Workflow after finishing a task

Do these steps in order after every completed change:

1. **Regression tests**: from `backend/`, run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest`. All must pass. Fix any failure before moving on.
2. **Security review**: run the `/security-review` skill on the change and fix real findings.
3. **Commit and push**: commit with a conventional message (`feat(...)`, `fix(...)`, `docs:`) and push to GitHub (`origin`). If you are on `main` or `dev`, create a feature branch first.

## Branches and deploy (ADR-0004)

`main` = production, `dev` = integration. Feature work goes in a PR to `dev`, and releases go in a PR from `dev` to `main`. Each branch maps to its own Railway environment and Supabase project. Production deploys are manual. Deployment uses `Dockerfile` with `railway.json`, and the Railway healthcheck is `/health`. In this repo, the `upstream` remote is the original project (JonathanZouari) and `origin` is the fork.
