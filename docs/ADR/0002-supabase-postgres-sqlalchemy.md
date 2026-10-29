# ADR 0002 — Supabase Postgres accessed via SQLAlchemy from the backend

Status: Proposed (adopted in Phase 2) · Date: 2026-10-29

## Context
Supabase is mandated. Options: supabase-py (PostgREST) or a direct Postgres connection with SQLAlchemy.

## Decision
The backend uses SQLAlchemy 2.x + psycopg against Supabase Postgres (`DATABASE_URL`). Supabase client/SDK used only where needed (Storage, Auth verification). Schema changes are SQL migrations in `database/migrations/`.

## Consequences
+ Real transactions and row locks (`SELECT … FOR UPDATE`), needed for safe proposal execution.
+ Testable with a local Postgres / Supabase CLI stack.
− RLS is defense-in-depth only, since the backend connects with a privileged role; authorization is enforced in services.
