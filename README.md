# AI Catering Platform

Ordering and management web app for a **single catering business**. Customers plan private events, pick dishes, get backend-calculated quantities and prices, and chat with an AI assistant whose suggested changes only apply after the customer approves them. The business owner manages the catalog and approves or rejects every quotation.

> Status: **Phase 1 — scaffolding**. No business features yet. See `docs/` for the specs.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic |
| Frontend | Plain HTML, CSS, JavaScript (served by FastAPI) |
| Data | SQLite now (Python's built-in `sqlite3`); Supabase (Postgres, Storage, Auth) planned |
| Hosting | Railway (Dockerfile build) |
| Quality | pytest, Ruff, GitHub Actions |

## Repository layout

```
backend/        FastAPI app (api, core, models, schemas, services, repositories, agents) + tests
frontend/       customer/ and admin/ pages, css/, js/, assets/
database/       migrations/ (SQLite schema) and seeds/ (sample data); catering.db is created here
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

- API health: http://127.0.0.1:8000/health
- Customer UI: http://127.0.0.1:8000/customer/
- Admin UI: http://127.0.0.1:8000/admin/
- Catalog API: http://127.0.0.1:8000/api/catalog/dishes

### Database

On startup the app creates `database/catering.db` and runs every SQL file in `database/migrations/`, then `database/seeds/`, that has not run yet. Each file runs once, in name order, and is recorded in the `schema_migrations` table. Set `SQLITE_PATH` to use another file. To start over, stop the app and delete `database/catering.db`.

Add a schema change as a new numbered file (`0002_….sql`); never edit a file that has already run.

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

The SQLite database uses Python's built-in `sqlite3`, so it needs no package. `sqlalchemy`, `psycopg`, and the Supabase client are added when the app moves to Supabase.

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
