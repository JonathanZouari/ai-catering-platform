-- Lead CRM: every submitted order is a lead, scored by the backend (services/lead_scoring.py).
-- The score is advisory. It never approves or rejects anything (ADR 0003).
-- Features hold numbers and flags only, never a name, phone, email or address.

create type lead_stage as enum ('new', 'qualified', 'won', 'lost');

create table leads (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete restrict,
    order_id uuid not null unique,
    stage lead_stage not null default 'new',
    score numeric(4, 3) not null check (score between 0 and 1),
    score_version text not null,
    reasons jsonb not null default '[]',
    features jsonb not null default '{}',
    scored_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    unique (caterer_id, id),
    foreign key (caterer_id, order_id) references orders (caterer_id, id) on delete cascade
);
create index leads_caterer_stage_idx on leads (caterer_id, stage);
create index leads_caterer_score_idx on leads (caterer_id, score desc);

-- Append-only history: stage changes and the caterer's notes.
create table lead_events (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null,
    lead_id uuid not null,
    kind text not null check (kind in ('stage_change', 'note')),
    stage lead_stage,
    note text,
    created_at timestamptz not null default now(),
    check (kind <> 'note' or note is not null),
    check (kind <> 'stage_change' or stage is not null),
    foreign key (caterer_id, lead_id) references leads (caterer_id, id) on delete cascade
);
create index lead_events_lead_idx on lead_events (caterer_id, lead_id, created_at);

-- The real outcome, with the score and features at that moment. This is the training data
-- for a future model, so it is written once and kept even if the caterer changes the stage.
create table lead_outcomes (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null,
    lead_id uuid not null unique,
    outcome lead_stage not null check (outcome in ('won', 'lost')),
    score_at_decision numeric(4, 3) not null,
    score_version text not null,
    features jsonb not null default '{}',
    decided_at timestamptz not null default now(),
    foreign key (caterer_id, lead_id) references leads (caterer_id, id) on delete cascade
);

alter table leads enable row level security;
alter table lead_events enable row level security;
alter table lead_outcomes enable row level security;

create policy "caterer reads own rows" on leads
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on lead_events
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on lead_outcomes
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));

-- The earlier "grant select on all tables" only covered tables that existed then.
-- Reads only: every write goes through FastAPI.
grant select on leads, lead_events, lead_outcomes to authenticated;
