# AI Catering Platform

Ordering and management web app for a **single catering business**. Customers plan private events, pick dishes, get backend-calculated quantities and prices, and chat with an AI assistant whose suggested changes only apply after the customer approves them. The business owner manages the catalog and approves or rejects every quotation.

> Status: **Customer quotations connected to Supabase or explicit local SQLite**. The form loads a normalized catalog, submits a priced quotation atomically and retrieves its receipt after restart. The owner admin reads the same cloud orders. AI execution, scheduling enforcement and order approval workflows remain unfinished. Operations/inventory are a separate optional extension. See `docs/DATABASE_SCHEMA.md` for review corrections and upgrade boundaries.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic, standard-library `sqlite3` |
| Frontend | Plain HTML, CSS, JavaScript (served by FastAPI) |
| Data | **Supabase Postgres** for cloud orders/admin; **SQLite** for explicit local mode. Auth, private Storage and Realtime support the owner interface. |
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

SQLite (3.37+) ships with Python. Cloud mode uses the pinned server HTTP client and a vendored browser SDK. Set `ORDER_DATABASE_BACKEND=supabase`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` and the server-only `SUPABASE_SECRET_KEY` in an ignored environment file. Never expose the secret key to the browser. Follow the reviewed migration procedure in `docs/DATABASE_SCHEMA.md` before connecting a fresh cloud database.

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
