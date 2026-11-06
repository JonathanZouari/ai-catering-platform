# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Ordering and management web app for a single catering business (Hebrew, RTL). Currently **Phase 6 (deploy)**: the Phase 2 admin screens, the Phase 3 customer ordering flow and the Phase 4 ordering assistant (Claude, `app/agents/`, OPEN #16 decided) are built; customer accounts use Supabase Auth (ADR 0005). The development environment runs on Railway `Dev` with Supabase `ai-catering-dev`; production isn't set up yet (`docs/DEPLOY.md`). The specs in `docs/` say what comes next and in which phase. Check `docs/OPEN_DECISIONS.md` before implementing anything marked **[OPEN]**, such as the logo.

## Working rules

1. **Plan before you execute.** Before writing any code, present a plan (scope, files to touch, how it will be verified) and wait for approval.
2. **After writing code, run E2E and regression tests.**
   - E2E: start the app (`uv run uvicorn app.main:app`) and drive the changed user flow in a real browser (Playwright MCP). Check the console for errors.
   - Regression: run the full `uv run pytest` and ruff checks, and re-check the existing pages (`/`, `/customer/`, `/admin/`) still work.
   - Report the actual results, including failures.
3. **Security review:** after each stage of code, run the `security-review` skill and fix or report what it finds.
4. **Document in Obsidian:** the project notes live in the Obsidian vault under `פלטפורמת קייטרינג AI/` (hub note: `פלטפורמת קייטרינג AI.md`). Every time you finish writing code, update the hub note's status and add a dated line to its change log (what changed, commit, test and security results). Add new notes in that folder for decisions or larger features.
   - A Stop hook (`.claude/settings.local.json`, git-ignored, this Windows machine only) runs `tools/obsidian_sync.py` after every response. It copies `docs/**/*.md` into the vault folder's `docs/` and regenerates `יומן commits.md` from `git log --all`. Both are overwritten on every sync, so never edit them in the vault. The hub note is never touched by the script, and its change log stays a manual step. The vault path defaults to `C:\Obsidian_Vault\פלטפורמת קייטרינג AI` (override it with `OBSIDIAN_PROJECT_DIR`). If the folder is missing, the script does nothing.

## Commands

All Python commands run from `backend/` with [uv](https://docs.astral.sh/uv/):

```bash
uv sync                                   # install deps (incl. dev group)
uv run uvicorn app.main:app --reload      # serves API + frontend at http://127.0.0.1:8000
uv run ruff check .                       # lint (E, F, I, B, UP, S; line length 100)
uv run ruff format --check .              # format check (CI fails on unformatted code)
uv run pytest                             # all tests
uv run pytest tests/test_health.py::test_health_ok   # single test
TEST_DATABASE_URL=<empty Postgres> uv run pytest   # suite on the real migrations (wipes that DB)
uv run python -m app.core.migrate [--dry-run]       # apply pending migrations to DATABASE_URL
```

CI (`.github/workflows/ci.yml`) runs `uv sync --frozen` → ruff check → ruff format --check → pytest on push/PR to `dev` and `main`. If you change dependencies, update `uv.lock`, because CI and the Dockerfile both use `--frozen`.

The frontend has no build step, bundler or package.json. `node --check frontend/js/<file>.js` is enough for a syntax check.

## Architecture

- **One FastAPI service serves everything.** `backend/app/main.py` registers API routes and then mounts `frontend/` at `/` with `StaticFiles(html=True)`. The mount must stay last so it does not shadow API routes. Because the frontend is same-origin, no CORS setup is needed. `FRONTEND_DIR` is resolved relative to `main.py`, so the Dockerfile keeps `backend/` and `frontend/` as siblings under `/srv`.
- **Layered monolith:** `api → services → repositories → models`, with `schemas/` (Pydantic DTOs and AI tool args) and `core/` (config). Lower layers never import upper ones. Most of these packages are still empty stubs and fill in during Phases 2–4 (`docs/ARCHITECTURE.md`).
- **New tables enable RLS** (`alter table ... enable row level security`, no policies) in their migration, so Supabase's anon key reaches nothing; the app connects as the table owner and is unaffected. `test_db.py` checks this on Postgres.
- **Schema changes come in threes.** Every change touches the model in `backend/app/models/`, a new numbered SQL file in `database/migrations/` (Postgres), and the diagram in `docs/ERD.md`, all in the same PR. Run the suite with `TEST_DATABASE_URL` on a new migration: the SQL is only exercised there.
  - Local SQLite only runs `create_all`, which adds missing tables but never alters existing ones. After adding a column, alter the local `dev.db` by hand or recreate it.
- **The backend is authoritative.** Prices, quantities, order state and availability are computed server-side only. The frontend and the LLM only display data or make requests (ADR 0003).
- **The AI agent (`agents/`, Phase 4) talks only to services, never to the database.** Tools are thin typed wrappers over services. The order ID is bound from the request context, never taken from model output. Mutations go through `propose_order_change`, which creates a pending proposal that the customer approves; execution happens in a single transaction (`docs/AI_AGENT_DESIGN.md`).
- **Config** comes from `core/config.py` (`get_settings()`, `lru_cache`d pydantic-settings). It reads `.env` from `backend/` or the repo root. DB and Supabase fields are optional until Phase 2.
- **API error shape** (`docs/API_CONTRACTS.md`): `{ "error": { "code", "message", "details" } }`. `frontend/js/api.js` relies on this shape when it builds thrown errors.

## Frontend conventions

- Plain HTML/CSS and ES modules, no framework (confirmed decision). Pages: `index.html` (landing), `customer/`, `admin/`. JS is imported by absolute path (`/js/...`).
- Every page is `<html lang="he" dir="rtl">` (a test checks this). Use **logical CSS properties only** (`margin-inline-start`, `inset-inline-end`), never left/right.
- The design system is **"Table Journal"** (editorial food-magazine look), specified in `docs/UX_UI_SPEC.md` §2, with tokens in `frontend/css/base.css`.
- Motion lives in `js/motion.js` (`initMotion`, `initRouteBand`), and all of it must stay static under `prefers-reduced-motion`. Hand-drawn icons are `<i data-ill="name">` placeholders that `hydrateIllustrations()` replaces with SVG from `js/illustrations.js`. Any new name must exist in its `ILL` map.
- `.impeccable/config.json` records confirmed design-lint exceptions. Example: the home page marquee is intentional, so keep it.
- `backend/tests/test_health.py` asserts that specific static paths are served. Update it if you rename or move pages, CSS, JS or images.

## Branches and deploy

- `dev` is for integration and maps to Railway `Dev` plus the dev Supabase project. `main` is production.
- Feature work goes as a PR into `dev`. Releases go as a PR from `dev` to `main`. Production deploys are manual and need explicit approval.
- Railway builds from the `Dockerfile` and runs a healthcheck on `/health`. Before each deploy, the service's pre-deploy command (set in the Railway dashboard; Railway ignores `railway.json` for new services) runs `python -m app.core.migrate`, which applies pending SQL migrations and records them in `schema_migrations`. Setup and variables: `docs/DEPLOY.md`.
- The Supabase service-role key is server-side only.
