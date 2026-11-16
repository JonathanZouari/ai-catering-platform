-- Leads: people who showed interest but have not become an order yet (docs/LEADS_DESIGN.md).
--   leads 1 ──< lead_events          (append-only activity log, same pattern as order_status_events)
--   leads.customer_id / leads.order_id are filled when a lead is converted (nullable, set null on delete).
-- Writes go through the backend (secret key, bypasses RLS), like orders. Admins can read only.
-- Anonymous visitors have no access: the public form posts to the API, never to the table.

-- ============================================================================
-- Tables
-- ============================================================================

create table public.leads (
  id                 text primary key default gen_random_uuid()::text,
  full_name          text not null check (char_length(btrim(full_name)) between 1 and 120),
  phone              text not null check (phone ~ '^\+[1-9][0-9]{7,14}$'),   -- E.164, normalized by the service
  email              text check (email is null or (char_length(email) <= 254 and email like '%_@_%')),
  source             text not null check (source in ('landing_form', 'abandoned_order', 'ai_chat', 'manual', 'whatsapp')),
  utm_source         text check (char_length(utm_source) <= 100),
  utm_medium         text check (char_length(utm_medium) <= 100),
  utm_campaign       text check (char_length(utm_campaign) <= 100),
  referrer           text check (char_length(referrer) <= 500),
  event_type_id      integer references public.event_types(id),
  event_date         date,                                  -- what the person said; not validated against availability
  approx_guests      integer check (approx_guests is null or approx_guests >= 1),
  budget_estimate    integer check (budget_estimate is null or budget_estimate > 0),   -- total for the event, agorot (like prices)
  message            text check (char_length(message) <= 2000),   -- free text for the owner; never parsed into safety claims
  status             text not null default 'new' check (status in ('new', 'contacted', 'quoted', 'won', 'lost')),
  lost_reason        text check (char_length(lost_reason) <= 500),
  customer_id        text references public.customers(id) on delete set null,
  order_id           text references public.orders(id) on delete set null,
  consent_marketing  boolean not null default false,
  consent_at         timestamptz,
  -- Output of the closing-probability model (docs/LEADS_DESIGN.md section 7). Written by the backend only,
  -- advisory: it never changes status. All four are null (not scored yet) or all set.
  conversion_probability  numeric(5,4) check (conversion_probability between 0 and 1),
  prediction_label        text check (prediction_label in ('won', 'lost')),   -- predicted class at the model threshold
  prediction_model_version text check (char_length(prediction_model_version) <= 100),
  predicted_at            timestamptz,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  check (lost_reason is null or status = 'lost'),
  check (not consent_marketing or consent_at is not null),
  check ((conversion_probability is null and prediction_label is null
          and prediction_model_version is null and predicted_at is null)
      or (conversion_probability is not null and prediction_label is not null
          and prediction_model_version is not null and predicted_at is not null))
);

create index idx_leads_status_created on public.leads (status, created_at desc);
create index idx_leads_customer       on public.leads (customer_id);
create index idx_leads_order          on public.leads (order_id);
create index idx_leads_event_type     on public.leads (event_type_id);
-- Admin list sorted by score, open leads only.
create index idx_leads_open_score     on public.leads (conversion_probability desc nulls last)
  where status in ('new', 'contacted', 'quoted');

-- One open lead per phone number: a repeat enquiry updates the open lead instead of creating a duplicate.
create unique index uq_leads_open_phone on public.leads (phone)
  where status in ('new', 'contacted', 'quoted');

create table public.lead_events (
  id             integer generated always as identity primary key,
  lead_id        text not null references public.leads(id) on delete cascade,
  type           text not null check (type in ('created', 'status_changed', 'note', 'converted')),
  from_status    text check (from_status in ('new', 'contacted', 'quoted', 'won', 'lost')),
  to_status      text check (to_status in ('new', 'contacted', 'quoted', 'won', 'lost')),
  actor          text not null check (actor in ('customer', 'owner', 'system')),
  admin_user_id  uuid references auth.users(id) on delete set null,
  note           text check (char_length(note) <= 2000),
  created_at     timestamptz not null default now(),
  check (type <> 'status_changed' or to_status is not null)
);
create index idx_lead_events_lead  on public.lead_events (lead_id, created_at);
create index idx_lead_events_admin on public.lead_events (admin_user_id);

-- ============================================================================
-- Training data for the closing-probability model: closed leads only, features known when the lead
-- arrived. status, lost_reason, the prediction columns and anything written after creation are NOT features
-- (they would leak the answer). Label: is_won.
-- ============================================================================

create view public.lead_training_data with (security_invoker = true) as
select
  l.id,
  l.created_at,
  l.source,
  l.utm_medium,
  et.name                                                   as event_type,
  l.approx_guests                                           as guests,
  l.budget_estimate,
  case when l.budget_estimate is not null and l.approx_guests > 0
       then l.budget_estimate / l.approx_guests end         as budget_per_guest,
  (l.event_date - l.created_at::date)                       as lead_time_days,
  (l.event_date is null)                                    as missing_event_date,
  (l.email is not null)                                     as has_email,
  (l.message is not null)                                   as has_message,
  l.consent_marketing,
  (l.status = 'won')                                        as is_won
from public.leads l
left join public.event_types et on et.id = l.event_type_id
where l.status in ('won', 'lost');

-- ============================================================================
-- Row level security: admin read only; every write goes through the backend.
-- ============================================================================

alter table public.leads       enable row level security;
alter table public.lead_events enable row level security;

-- Supabase grants broad default privileges on new public tables; keep only what is needed (defense in depth on top of RLS).
revoke all on public.leads, public.lead_events, public.lead_training_data from anon, authenticated;
grant select on public.leads, public.lead_events, public.lead_training_data to authenticated;

create policy "admin read" on public.leads
  for select to authenticated using ((select public.is_admin()));
create policy "admin read" on public.lead_events
  for select to authenticated using ((select public.is_admin()));
