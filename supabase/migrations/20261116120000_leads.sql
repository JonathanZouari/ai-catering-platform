-- Leads: people who asked about catering an event, before any order exists.
-- A lead is "won" when it ended in an approved order and "lost" when it did not.
-- Not linked to customers or orders yet. Documented in docs/DATABASE_SCHEMA.md.

create type lead_status as enum ('new', 'contacted', 'quoted', 'won', 'lost');
create type lead_source as enum ('referral', 'google', 'instagram', 'website');

create table leads (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  phone text,
  email text,
  -- Same labels as events.event_type (the customer event form).
  event_type text not null,
  event_date date not null,
  guests int not null check (guests > 0),
  budget_per_guest numeric(10,2) not null check (budget_per_guest >= 0),
  source lead_source not null,
  is_returning boolean not null default false,
  status lead_status not null default 'new',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index leads_status_idx on leads (status);

create trigger leads_updated_at before update on leads
  for each row execute function set_updated_at();

-- Access: the admin only. Leads hold names and phone numbers, so customers read nothing.
-- The only client write is the admin changing a lead's status.
alter table leads enable row level security;

revoke all on leads from anon, authenticated;
grant select on leads to authenticated;
grant update (status) on leads to authenticated;

create policy "admin reads" on leads for select to authenticated
  using ((select private.is_admin()));
create policy "admin updates" on leads for update to authenticated
  using ((select private.is_admin())) with check ((select private.is_admin()));
