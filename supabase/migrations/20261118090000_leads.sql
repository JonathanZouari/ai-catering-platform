-- yumm.ai: lead management. Documented in docs/LEAD_MANAGEMENT.md.
-- Leads are an owner-only (admin) CRM layer. Customers never read or write them.
-- Scores are advisory: they never change order state, price or approval.

create type lead_stage as enum ('new', 'contacted', 'quoted', 'negotiating', 'won', 'lost');
create type lead_source as enum (
  'website_form', 'ai_chat', 'whatsapp', 'phone', 'referral', 'instagram', 'google'
);

create table leads (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid references customers (id),       -- set once the lead has an account
  order_id uuid unique references orders (id),      -- set on conversion; the label for the model
  full_name text not null,
  email text,
  phone text,
  source lead_source not null,
  stage lead_stage not null default 'new',
  lost_reason text,
  event_type text,
  event_date date,
  guests int check (guests is null or guests > 0),
  budget numeric(10,2) check (budget is null or budget >= 0),
  notes text,
  first_response_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (stage <> 'lost' or lost_reason is not null),
  check (stage <> 'won' or order_id is not null)
);
create index leads_stage_idx on leads (stage);
create index leads_created_at_idx on leads (created_at desc);
create trigger leads_set_updated_at before update on leads
  for each row execute function set_updated_at();

-- Append-only activity log. Feature source for scoring, audit trail for the owner.
create table lead_activities (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references leads (id) on delete cascade,
  kind text not null check (kind in
    ('note', 'call', 'message', 'quote_sent', 'stage_change', 'menu_viewed', 'chat_started')),
  detail jsonb not null default '{}',
  created_at timestamptz not null default now()
);
create index lead_activities_lead_id_idx on lead_activities (lead_id, created_at);

-- One row per scoring run, so scores can be audited and models compared over time.
create table lead_scores (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references leads (id) on delete cascade,
  model text not null,                 -- e.g. 'logreg-v1', 'hgb-v1'
  probability numeric(5,4) not null check (probability between 0 and 1),
  features jsonb not null,             -- exact inputs, for explainability
  scored_at timestamptz not null default now()
);
create index lead_scores_lead_id_idx on lead_scores (lead_id, scored_at desc);

alter table leads enable row level security;
alter table lead_activities enable row level security;
alter table lead_scores enable row level security;

create policy "admin all" on leads for all to authenticated
  using ((select private.is_admin())) with check ((select private.is_admin()));
create policy "admin all" on lead_activities for all to authenticated
  using ((select private.is_admin())) with check ((select private.is_admin()));
create policy "admin all" on lead_scores for all to authenticated
  using ((select private.is_admin())) with check ((select private.is_admin()));
