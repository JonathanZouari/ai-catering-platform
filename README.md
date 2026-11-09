# AI Catering Platform

Ordering and management web app for a **single catering business**. Customers plan private events, pick dishes, get backend-calculated quantities and prices, and chat with an AI assistant whose suggested changes only apply after the customer approves them. The business owner manages the catalog and approves or rejects every quotation.

> Status: **Phase 1 — scaffolding**. No business features yet. See `docs/` for the specs.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic (Postgres access added in Phase 2) |
| Frontend | Plain HTML, CSS, JavaScript (served by FastAPI) |
| Data | Supabase (Postgres, Auth, Storage, Realtime) in every environment. Schema in `supabase/migrations/` |
| Hosting | Railway (Dockerfile build) |
| Quality | pytest, Ruff, GitHub Actions |

## Repository layout

```
backend/        FastAPI app (api, core, models, schemas, services, repositories, agents) + tests
frontend/       customer/ and admin/ pages, css/, js/, assets/
supabase/       migrations/ (SQL, Supabase CLI), seed.sql (synthetic demo data), config.toml
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
- Admin UI: http://127.0.0.1:8000/admin/ (staff login)
- Login: http://127.0.0.1:8000/login/
- Customer account: http://127.0.0.1:8000/account/ (customer login)

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

`psycopg` (and optionally `sqlalchemy`) is added to the backend when its database code exists. The browser loads `supabase-js` from a pinned CDN URL in `frontend/js/auth.js`.

### Database (Supabase)

The schema and the demo data live in `supabase/`. The repo is linked to the `ai-catering-dev` project. Install the [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started) first.

```bash
supabase migration new <name>            # write a new migration (never edit an applied one)
supabase db push --remote                # apply new migrations to the linked project
supabase db query --remote -f supabase/seed.sql   # load demo data into an empty database
supabase db advisors --remote            # security and performance checks before merging
supabase start && supabase db reset      # optional: full local copy (needs Docker)
```

The database password for the CLI goes in `SUPABASE_DB_PASSWORD` (see `.env.example`). Demo logins for staff and a customer exist in the dev project. Ask the owner for the passwords.

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

- **Supabase:** the repo is linked to the `ai-catering-dev` project. All migrations in `supabase/migrations/` are applied there, along with the demo data. The production project does not exist yet.
- **Railway:** configuration templates only (`railway.json`, `Dockerfile`, `.env.example`). No Railway project is connected yet. That is planned for Phase 6.

## Documentation

- [PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [Database schema](docs/DATABASE_SCHEMA.md) · [API contracts](docs/API_CONTRACTS.md)
- [AI agent design](docs/AI_AGENT_DESIGN.md) · [UX/UI spec](docs/UX_UI_SPEC.md) · [Open decisions](docs/OPEN_DECISIONS.md) · [ADRs](docs/ADR/)
