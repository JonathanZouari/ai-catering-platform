-- Leads: short "call me back" inquiries (docs/LEADS_PLAN.md). Not orders: no prices, no status shared with orders.
-- Access: only the admin reads and writes. Public submissions will go through the backend, never a direct client write.

create type lead_source as enum ('landing_form', 'ai_chat', 'manual');
create type lead_status as enum ('new', 'contacted', 'converted', 'lost');

create table leads (
  id uuid primary key default gen_random_uuid(),
  full_name text not null check (char_length(btrim(full_name)) between 1 and 100),
  -- E.164 Israeli numbers: mobile +9725XXXXXXXX, landline +972[2-4,8,9]XXXXXXX, 07X +9727XXXXXXXX.
  phone text not null check (phone ~ '^\+972[2-9][0-9]{7,8}$'),
  email text check (char_length(email) <= 254 and email ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'),
  event_type text check (char_length(btrim(event_type)) between 1 and 50),
  event_date date,
  guest_count int check (guest_count between 1 and 5000),
  message text check (char_length(message) <= 1000),
  source lead_source not null,
  status lead_status not null default 'new',
  lost_reason text check (char_length(lost_reason) <= 500),
  customer_id uuid references customers (id) on delete set null,
  consent_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint leads_lost_needs_reason check (status <> 'lost' or coalesce(char_length(btrim(lost_reason)), 0) > 0),
  constraint leads_public_needs_consent check (source = 'manual' or consent_at is not null)
);

create index leads_status_created_idx on leads (status, created_at desc);
create index leads_phone_idx on leads (phone);
create index leads_customer_idx on leads (customer_id);

create table lead_notes (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references leads (id) on delete cascade,
  author_id uuid references auth.users (id) on delete set null,
  body text not null check (char_length(btrim(body)) between 1 and 2000),
  created_at timestamptz not null default now()
);

create index lead_notes_lead_idx on lead_notes (lead_id, created_at);
create index lead_notes_author_idx on lead_notes (author_id);

create trigger leads_updated_at before update on leads
  for each row execute function set_updated_at();

alter table leads enable row level security;
alter table lead_notes enable row level security;

-- New tables get Supabase's default grants, so take them back explicitly. Notes are append-only.
revoke all on leads, lead_notes from anon;
revoke delete, truncate on leads from authenticated;
revoke update, delete, truncate on lead_notes from authenticated;

create policy "admin reads" on leads for select to authenticated
  using ((select private.is_admin()));
create policy "admin inserts" on leads for insert to authenticated
  with check ((select private.is_admin()));
create policy "admin updates" on leads for update to authenticated
  using ((select private.is_admin())) with check ((select private.is_admin()));

create policy "admin reads" on lead_notes for select to authenticated
  using ((select private.is_admin()));
create policy "admin writes own notes" on lead_notes for insert to authenticated
  with check ((select private.is_admin()) and author_id = (select auth.uid()));

-- Live "new lead" badge in the admin. Realtime respects the policies above.
alter publication supabase_realtime add table leads;
