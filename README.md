# AI Catering Platform

Ordering and management web app for a **single catering business**. Customers plan private events, pick dishes, get backend-calculated quantities and prices, and chat with an AI assistant whose suggested changes only apply after the customer approves them. The business owner manages the catalog and approves or rejects every quotation.

> Status: **Phase 1 — scaffolding**. No business features yet. See `docs/` for the specs.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic |
| Frontend | Plain HTML, CSS, JavaScript (served by FastAPI), vendored supabase-js |
| Data | Supabase (Postgres, Auth, Storage, Realtime) |
| Hosting | Railway (Dockerfile build) |
| Quality | pytest, Ruff, GitHub Actions |

## Repository layout

```
backend/        FastAPI app (api, core, models, schemas, services, repositories, agents) + tests
frontend/       login/, customer/ and admin/ pages, css/, js/, assets/
supabase/       CLI config, migrations/ and seed.sql (synthetic data)
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

`sqlalchemy` and `psycopg` are added when backend database code exists. Today the browser talks to Supabase directly, protected by RLS.

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

Railway: configuration templates only (`railway.json`, `Dockerfile`, `.env.example`). No Railway project is connected yet. That is planned for Phase 6.

Supabase: the dev project `ai-catering-dev` (organization `yumm.ai`, region `eu-central-1`) is live. There is no prod project yet.

To set up a Supabase project from scratch, fill `.env`, then:

```bash
supabase link --project-ref <ref>
supabase db push --linked
supabase config push                                              # dev auth settings; see the note below
(cd backend && uv run --env-file ../.env python scripts/create_demo_users.py)
supabase db query --linked -f supabase/seed.sql                  # dev only: synthetic data
(cd backend && uv run --env-file ../.env pytest)                 # includes live access-control tests
```

`supabase/config.toml` turns email confirmation off, because Supabase's built-in email only reaches organization members. Before production, set up custom SMTP and enable confirmations. Do not load the seed or create the demo users in production.

## Documentation

- [PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [Database schema](docs/DATABASE_SCHEMA.md) · [API contracts](docs/API_CONTRACTS.md)
- [AI agent design](docs/AI_AGENT_DESIGN.md) · [UX/UI spec](docs/UX_UI_SPEC.md) · [Open decisions](docs/OPEN_DECISIONS.md) · [ADRs](docs/ADR/)
