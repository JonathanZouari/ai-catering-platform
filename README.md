# AI Catering Platform

Ordering and management web app for a **single catering business**. Customers plan private events, pick dishes, get backend-calculated quantities and prices, and chat with an AI assistant whose suggested changes only apply after the customer approves them. The business owner manages the catalog and approves or rejects every quotation.

> Status: **Phase 1 — scaffolding**. No business features yet. See `docs/` for the specs.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic (SQLAlchemy added in Phase 2) |
| Frontend | Plain HTML, CSS, JavaScript (served by FastAPI) |
| Data | Supabase (Postgres, Storage, Auth when approved) |
| Hosting | Railway (Dockerfile build) |
| Quality | pytest, Ruff, GitHub Actions |

## Repository layout

```
backend/        FastAPI app (api, core, models, schemas, services, repositories, agents) + tests
frontend/       customer/ and admin/ pages, css/, js/, assets/
database/       migrations/ (SQL, Supabase CLI format — first migration in Phase 2)
docs/           PRD, architecture, schema, API, AI agent, UX/UI, ADRs, open decisions
.github/        CI workflow
Dockerfile      Production image used by Railway
railway.json    Railway build/deploy config (healthcheck /health)
.env.example    Environment variable template
```

## Local development

Requires [uv](https://docs.astral.sh/uv/) (it installs a matching Python automatically).

```bash
cp .env.example .env          # fill values when needed; .env is git-ignored
cd backend
uv sync                       # install dependencies
uv run uvicorn app.main:app --reload
```

Without `DATABASE_URL` the backend uses a local SQLite file, `backend/catering.db`. Create the catalog tables (dish categories, dishes) and the demo menu with:

```bash
cd backend
uv run python -m app.seed      # safe to re-run
```

- API health: http://127.0.0.1:8000/health
- Customer UI: http://127.0.0.1:8000/customer/
- Admin UI: http://127.0.0.1:8000/admin/

### Tests and lint

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Dependencies and why

| Package | Why |
|---|---|
| `fastapi` | Mandated web framework |
| `uvicorn[standard]` | ASGI server for FastAPI |
| `pydantic-settings` | Typed config from environment variables |
| `pytest` (dev) | Mandated test runner |
| `httpx` (dev) | Needed by FastAPI's `TestClient` |
| `ruff` (dev) | Mandated linter/formatter |

`sqlalchemy`, `psycopg`, and the Supabase client are added in Phase 2, when database code exists.

## Branches and environments

| Branch | Purpose | Railway env | Supabase project |
|---|---|---|---|
| `main` | Production (default branch) | `production` | prod project |
| `dev` | Integration | `development` | dev project |

- Feature work → PR into `dev` (CI must pass).
- Release → PR `dev` → `main`.
- Production deploys are manual and need explicit approval.
- Each Railway environment holds its own variables from `.env.example`. **Never commit secrets.** The service-role key stays server-side.

## Railway / Supabase status

Configuration templates only (`railway.json`, `Dockerfile`, `.env.example`). No Railway project or Supabase project is connected yet. That is planned for Phase 6.

## Documentation

- [PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [Database schema](docs/DATABASE_SCHEMA.md) · [API contracts](docs/API_CONTRACTS.md)
- [AI agent design](docs/AI_AGENT_DESIGN.md) · [UX/UI spec](docs/UX_UI_SPEC.md) · [Open decisions](docs/OPEN_DECISIONS.md) · [ADRs](docs/ADR/)

## Supabase (dev project)

The dev project is **ai-catering-dev** (organization YummaiTal, region eu-central-1). Schema changes are SQL files in `database/migrations/`, applied in filename order to the dev project, then to prod at release time:

```bash
supabase db query --remote=<project-ref> -f database/migrations/<file>.sql
supabase db advisors --remote=<project-ref>      # run after every change
```

- **RLS**: the catalog is public to read and owner-only to write. The owner is a user whose `app_metadata.role` is `owner` (set with the secret key only; `user_metadata` is user-editable and never trusted).
- **Realtime**: every catalog write bumps one row in `catalog_changes`; open customer menus subscribe to it and refetch.
- **Storage**: `dish-images` (public, 5 MB, JPEG/PNG/WebP) and `signed-quotes` (private, 10 MB, PDF/JPEG/PNG). Neither has browser write policies; uploads go through the backend.
- **Owner screen**: `/admin/` signs in with Supabase Auth and uploads dish photos.
