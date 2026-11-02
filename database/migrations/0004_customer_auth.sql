-- Customer accounts via Supabase Auth (passwordless email code, ADR 0005).
-- A customer row is linked to auth.users once the customer completes the profile.
-- Null for customers created without an account (e.g. sample data).

alter table customers
  add column auth_user_id uuid unique references auth.users(id) on delete set null;
