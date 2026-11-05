# ADR 0004 — Branches, environments, and deploy flow

Status: Accepted (Phase 0) · Date: 2026-10-29

## Decision
- `main` = production (default branch). `dev` = integration.
- Work → PR into `dev`; release → PR `dev` → `main`. CI (Ruff + pytest) must pass.
- `dev` ↔ Railway `development` ↔ its own SQLite file; `main` ↔ Railway `production` ↔ its own SQLite file (ADR 0005; originally separate Supabase projects).
- Production deploys are manual and need explicit approval.

## Consequences
+ Test data never touches production.
− Two databases to keep schema-synced via the same migrations (applied automatically on startup).
