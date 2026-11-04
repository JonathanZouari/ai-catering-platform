# AI Catering Platform

Ordering and management web app for a **single catering business**. Customers plan private events, pick dishes, get backend-calculated quantities and prices, and chat with an AI assistant whose suggested changes only apply after the customer approves them. The business owner manages the catalog and approves or rejects every quotation.

> Status: **Customer quotation persistence connected**. The customer form loads the catalog from SQLite, submits a priced quotation atomically, and retrieves its receipt after restart. The assistant and availability rules remain demonstrations; owner approval/admin workflows are not implemented. See `docs/` for the specs.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic, standard-library `sqlite3` |
| Frontend | Plain HTML, CSS, JavaScript (served by FastAPI) |
| Data | **SQLite** ([ADR 0005](docs/ADR/0005-sqlite-database.md)). Supabase Storage/Auth optional, if approved |
| Hosting | Railway (Dockerfile build) |
| Quality | pytest, Ruff, GitHub Actions |

## Repository layout

```
backend/        FastAPI app (api, core, db, models, schemas, services, repositories, agents) + tests
frontend/       customer/ and admin/ pages, css/, js/, assets/
database/       migrations/NNNN_name.sql (SQLite, forward-only)
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
uv run python -m app.db       # create/upgrade data/catering.sqlite3 (safe to repeat)
uv run uvicorn app.main:app --reload
```

The app also applies pending migrations on startup (`DB_AUTO_MIGRATE=true`). Migrations never drop
data; `uv run python -m app.db status` lists what is applied. Schema and rules:
[docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md).

- API health (includes database status): http://127.0.0.1:8000/health
- Customer UI: http://127.0.0.1:8000/customer/
- Admin UI: http://127.0.0.1:8000/admin/

### Tests and lint

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest
# From repository root, with Node 22+:
node --test frontend/tests/order-store.test.mjs
```

## Dependencies and why

| Package | Why |
|---|---|
| `fastapi` | Mandated web framework |
| `uvicorn[standard]` | ASGI server for FastAPI |
| `pydantic-settings` | Typed config from environment variables |
| `tzdata` | Convert Israel event times correctly on Windows and Linux |
| `pytest` (dev) | Mandated test runner |
| `httpx` (dev) | Needed by FastAPI's `TestClient` |
| `ruff` (dev) | Mandated linter/formatter |

The database needs no extra package: SQLite (3.37+) ships with Python. The Supabase client is added only if Storage/Auth are adopted.

## Branches and environments

| Branch | Purpose | Railway env | Database |
|---|---|---|---|
| `main` | Production (default branch) | `production` | own SQLite file (volume) |
| `dev` | Integration | `development` | own SQLite file (volume) |

- Feature work → PR into `dev` (CI must pass).
- Release → PR `dev` → `main`.
- Production deploys are manual and need explicit approval.
- Each Railway environment holds its own variables from `.env.example`. **Never commit secrets.** The service-role key stays server-side.

## Railway status

Configuration templates only (`railway.json`, `Dockerfile`, `.env.example`). No Railway project is connected yet. That is planned for Phase 6. Railway's container disk is ephemeral, so each environment needs a volume, with `SQLITE_PATH` pointing into it (the image defaults to `/srv/data/catering.sqlite3`).

## Documentation

- [PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [Database schema](docs/DATABASE_SCHEMA.md) · [API contracts](docs/API_CONTRACTS.md)
- [AI agent design](docs/AI_AGENT_DESIGN.md) · [UX/UI spec](docs/UX_UI_SPEC.md) · [Open decisions](docs/OPEN_DECISIONS.md) · [ADRs](docs/ADR/)
