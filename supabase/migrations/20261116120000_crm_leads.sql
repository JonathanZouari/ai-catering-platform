-- CRM leads: one row per prospective customer, with the signals used for purchase prediction.
-- Admin-only: leads are business-internal and never visible to customers.

create type lead_source as enum ('web', 'referral', 'phone', 'ad');
create type lead_event_type as enum ('wedding', 'birthday', 'corporate', 'bar_mitzvah', 'other');
create type lead_stage as enum ('new', 'engaged', 'quote_requested', 'quote_sent', 'won', 'lost');

create table leads (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid references customers (id) on delete set null,
  source lead_source not null,
  event_type lead_event_type not null,
  days_until_event int not null check (days_until_event >= 0),
  guest_count int not null check (guest_count > 0),
  dishes_selected int not null default 0 check (dishes_selected >= 0),
  quote_submitted boolean not null default false,
  ai_chat_messages int not null default 0 check (ai_chat_messages >= 0),
  visits_last_7d int not null default 0 check (visits_last_7d >= 0),
  days_since_last_activity int not null default 0 check (days_since_last_activity >= 0),
  has_phone boolean not null default false,
  has_email boolean not null default false,
  stage lead_stage not null default 'new',
  is_buyer boolean,                                  -- outcome label; null while the lead is open
  score numeric(5, 4) check (score between 0 and 1), -- model probability
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  closed_at timestamptz
);

create index leads_customer_id_idx on leads (customer_id);
create index leads_stage_idx on leads (stage);
create index leads_score_idx on leads (score desc);

create trigger leads_updated_at before update on leads
  for each row execute function set_updated_at();

alter table leads enable row level security;
create policy "admin all" on leads for all to authenticated
  using ((select private.is_admin())) with check ((select private.is_admin()));
