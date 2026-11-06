# ADR 0002 — Supabase Postgres in every environment

Status: Accepted · Date: 2026-10-29 · Revised: 2026-11-02 (SQLite for local dev) · Revised: 2026-11-06 (SQLite dropped; Supabase only)

## Context
Supabase is mandated for production. The 2026-11-02 revision added SQLite for local development, which forced a portable schema: text + CHECK instead of enums, `json` instead of `jsonb`, no RLS, and staff passwords stored in our own table.

On 2026-11-05 the schema was built directly in Supabase (project `ai-catering-dev`) with Supabase Auth, RLS, Storage and Realtime. Those features have no SQLite equivalent, so keeping SQLite would mean maintaining two security models. On 2026-11-06 the owner decided to drop SQLite.

## Decision
- **One database engine: Supabase Postgres**, in every environment. Local development uses either the `ai-catering-dev` project or the local Supabase stack (`supabase start`, Docker). Tests run against the local stack.
- **Schema source: `supabase/migrations/`**, plain SQL written with the Supabase CLI (`supabase migration new`), applied with `supabase db push`. Synthetic data lives in `supabase/seed.sql`. There is no Alembic and no model-generated migration.
- **Postgres features are used where they help:** enum types, `jsonb`, partial indexes, triggers, `security definer` helpers in a non-exposed `private` schema.
- **Login: Supabase Auth** for staff and customers. A user is staff when they have an active row in `staff_users` (whose `id` is the `auth.users` id). A customer is linked through `customers.auth_user_id`. Roles are never read from `user_metadata`, which users can edit.
- **Two ways in, one set of rules:**
  - The **browser** uses `supabase-js` with the publishable key for login, reading the menu, staff admin screens, dish-image upload and Realtime. Row Level Security decides what each request may see or change.
  - The **FastAPI backend** connects directly (`DATABASE_URL`) with a privileged role for everything that must be computed server-side: pricing, order submission, the daily capacity check and AI proposal execution (ADR-0003). SQLAlchemy 2.x with `psycopg` may be used to query, mapped onto the existing tables; it never creates or alters them.
- **Storage:** public bucket `dish-images` (5 MB, JPEG/PNG/WEBP). Anyone can view; only staff can upload, replace or delete.
- **Realtime:** enabled on `orders` and `order_events`. Updates follow the same RLS read rules.

## Consequences
+ One schema and one security model. RLS is now the real access control for browser traffic, not just defense in depth.
+ Enums, `jsonb` and triggers catch bad data in the database itself.
+ Staff screens can read and write simple data without a backend endpoint for each action.
− Local development needs Docker (local stack) or network access to the dev project. There is no zero-setup database file.
− RLS policies must be reviewed with every schema change, and `supabase db advisors` run before each migration is merged.
− Removing a value from an enum needs a new type. Adding one is a single `alter type … add value`.
− Customers must not write orders directly: the backend stays the only writer for anything priced or capacity-limited (ADR-0003).
