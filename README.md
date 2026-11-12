# AI Catering Platform

Ordering and management web app for a **single catering business**. Customers plan private events, pick dishes, get backend-calculated quantities and prices, and chat with an AI assistant whose suggested changes only apply after the customer approves them. The business owner manages the catalog and approves or rejects every quotation.

> Status: **Phase 1 — scaffolding**. No business features yet. See `docs/` for the specs.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic |
| Frontend | Plain HTML, CSS, JavaScript (served by FastAPI) |
| Data | Supabase Postgres through SQLAlchemy and psycopg; Supabase Storage bucket for dish images (no upload yet); Auth planned |
| Hosting | Railway (Dockerfile build) |
| Quality | pytest, Ruff, GitHub Actions |

## Repository layout

```
backend/        FastAPI app (api, core, models, schemas, services, repositories, agents) + tests
frontend/       customer/ and admin/ pages, css/, js/, assets/
database/       migrations/ (Postgres schema) and seeds/ (sample data)
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

The app needs `DATABASE_URL` in `.env` and does not start without it (see `.env.example`). On startup it runs every SQL file in `database/migrations/`, then `database/seeds/`, that has not run yet. Each file runs once, in name order, and is recorded in the `schema_migrations` table. All pending files run in one transaction, so a failure leaves nothing behind.

Add a schema change as a new numbered file (`0002_….sql`); never edit a file that has already run.

### Storage

Dish images go in a public Supabase Storage bucket, `dish-images`. It is not created by the migrations, because CI's plain Postgres has no `storage` schema. Run this once in each Supabase project (SQL Editor):

```sql
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('dish-images', 'dish-images', true, 5242880, array['image/jpeg', 'image/png', 'image/webp']);
```

Anyone can view a file by its link. With no policies on `storage.objects`, the public cannot upload. The upload endpoint is not built yet; it waits for admin login (OPEN #1).

### Tests and lint

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Database tests need `DATABASE_URL` and are skipped without it. Each test builds its own throwaway schema and drops it afterwards, so existing tables are not touched.

## Dependencies and why

| Package | Why |
|---|---|
| `fastapi` | Mandated web framework |
| `uvicorn[standard]` | ASGI server for FastAPI |
| `pydantic-settings` | Typed config from environment variables |
| `sqlalchemy` | Database connections and pooling (ADR 0002) |
| `psycopg[binary]` | Postgres driver for SQLAlchemy (ADR 0002) |
| `pytest` (dev) | Mandated test runner |
| `httpx` (dev) | Needed by FastAPI's `TestClient` |
| `ruff` (dev) | Mandated linter/formatter |

The Supabase client is added when the app needs Storage or Auth.

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
