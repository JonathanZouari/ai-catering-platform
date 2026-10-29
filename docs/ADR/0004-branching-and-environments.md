# ADR 0004 — Branches, environments, and deploy flow

Status: Accepted (Phase 0) · Date: 2026-10-29

## Decision
- `main` = production (default branch). `dev` = integration.
- Work → PR into `dev`; release → PR `dev` → `main`. CI (Ruff + pytest) must pass.
- `dev` ↔ Railway `development` ↔ Supabase dev project; `main` ↔ Railway `production` ↔ Supabase prod project.
- Production deploys are manual and need explicit approval.

## Consequences
+ Test data never touches production.
− Two Supabase projects to keep schema-synced via the same migrations.
