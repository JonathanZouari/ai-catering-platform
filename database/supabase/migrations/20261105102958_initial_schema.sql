-- Initial schema — implements docs/DATABASE_SCHEMA.md (Draft v0.1).
-- Access model (ADR 0002): the backend connects with a privileged role and
-- enforces authorization in services. RLS is enabled on every table with no
-- policies, so the public Data API (anon/authenticated) sees nothing.
-- Not included yet: quantity_rules (OPEN #3, shape not designed).

-- ---------------------------------------------------------------- helpers
create schema if not exists private;

create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------- enums
create type public.pricing_unit     as enum ('per_guest', 'per_tray', 'per_weight', 'per_item');
create type public.kashrut_class    as enum ('meat', 'dairy', 'pareve');
create type public.fulfillment_type as enum ('pickup', 'delivery');
create type public.order_status     as enum ('draft', 'pending_approval', 'approved', 'rejected');
create type public.proposal_status  as enum ('pending', 'approved', 'rejected', 'expired', 'failed');
create type public.allergen_status  as enum ('contains', 'free', 'unknown');

-- ---------------------------------------------------------------- customers
create table public.customers (
  id           uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique references auth.users (id) on delete set null, -- OPEN #1
  full_name    text not null,
  email        text,
  phone        text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------- events
create table public.events (
  id                uuid primary key default gen_random_uuid(),
  customer_id       uuid not null references public.customers (id) on delete restrict,
  event_type        text not null,
  event_date        date not null,
  adults            int  not null check (adults >= 0),
  children          int  not null check (children >= 0),
  vegetarian_guests int  not null default 0 check (vegetarian_guests >= 0), -- OPEN #4
  vegan_guests      int  not null default 0 check (vegan_guests >= 0),      -- OPEN #4
  restricted_guests int  not null default 0 check (restricted_guests >= 0),
  dietary_notes     text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  constraint events_has_guests check (adults + children > 0)
);
create index events_customer_id_idx on public.events (customer_id);

-- ---------------------------------------------------------------- menu
create table public.dish_categories (
  id         uuid primary key default gen_random_uuid(),
  name       text not null unique,
  sort_order int  not null default 0,
  is_active  bool not null default true
);

create table public.dishes (
  id           uuid primary key default gen_random_uuid(),
  category_id  uuid not null references public.dish_categories (id) on delete restrict,
  name         text not null,
  description  text,
  image_path   text,                                   -- Supabase Storage object path
  pricing_unit public.pricing_unit not null,
  unit_price   numeric(10,2) not null check (unit_price >= 0),
  unit_label   text,                                   -- OPEN #18
  currency     char(3) not null default 'ILS',         -- OPEN #17
  min_quantity numeric(10,2) check (min_quantity > 0), -- OPEN #15
  is_available bool not null default true,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index dishes_category_id_idx on public.dishes (category_id);

-- Null = unknown; must be shown as unknown, never as yes/no.
create table public.dish_dietary (
  dish_id       uuid primary key references public.dishes (id) on delete cascade,
  kashrut_class public.kashrut_class,
  is_vegetarian bool,
  is_vegan      bool,
  verified_at   timestamptz
);

create table public.allergens (
  id   smallint generated always as identity primary key,
  name text not null unique
);

-- Missing row = unknown.
create table public.dish_allergens (
  dish_id     uuid     not null references public.dishes (id) on delete cascade,
  allergen_id smallint not null references public.allergens (id) on delete restrict,
  status      public.allergen_status not null,
  primary key (dish_id, allergen_id)
);
create index dish_allergens_allergen_id_idx on public.dish_allergens (allergen_id);

-- ---------------------------------------------------------------- logistics
create table public.delivery_zones (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  fee        numeric(10,2) not null check (fee >= 0),
  definition jsonb not null, -- OPEN #19
  is_active  bool not null default true
);

create table public.time_slots (
  id               uuid primary key default gen_random_uuid(),
  fulfillment_type public.fulfillment_type not null,
  weekday          smallint check (weekday between 0 and 6),
  start_time       time not null,
  end_time         time not null,
  capacity         int check (capacity >= 0), -- OPEN #5
  is_active        bool not null default true,
  constraint time_slots_valid_range check (end_time > start_time)
);

create table public.blocked_dates (
  id     uuid primary key default gen_random_uuid(),
  date   date not null unique,
  reason text
);

-- ---------------------------------------------------------------- orders
create table public.orders (
  id               uuid primary key default gen_random_uuid(),
  customer_id      uuid not null references public.customers (id) on delete restrict,
  event_id         uuid not null unique references public.events (id) on delete restrict,
  status           public.order_status not null default 'draft',
  version          int  not null default 1,
  fulfillment_type public.fulfillment_type not null,
  requested_at     timestamptz not null,
  delivery_address text,
  delivery_zone_id uuid references public.delivery_zones (id) on delete restrict,
  subtotal         numeric(10,2) check (subtotal >= 0),
  delivery_fee     numeric(10,2) check (delivery_fee >= 0),
  total            numeric(10,2) check (total >= 0),
  submitted_at     timestamptz,
  decided_at       timestamptz,
  decision_note    text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint orders_delivery_needs_address
    check (fulfillment_type <> 'delivery' or delivery_address is not null)
);
create index orders_customer_id_idx      on public.orders (customer_id);
create index orders_status_idx           on public.orders (status);
create index orders_delivery_zone_id_idx on public.orders (delivery_zone_id);

-- While draft, prices come live from dishes; snapshot_* is authoritative from submission.
create table public.order_items (
  id                    uuid primary key default gen_random_uuid(),
  order_id              uuid not null references public.orders (id) on delete cascade,
  dish_id               uuid not null references public.dishes (id) on delete restrict,
  quantity              numeric(10,2) not null check (quantity > 0),
  snapshot_name         text,
  snapshot_pricing_unit public.pricing_unit,
  snapshot_unit_price   numeric(10,2),
  snapshot_line_total   numeric(10,2),
  unique (order_id, dish_id)
);
create index order_items_dish_id_idx on public.order_items (dish_id);

-- ---------------------------------------------------------------- AI
create table public.ai_conversations (
  id         uuid primary key default gen_random_uuid(),
  order_id   uuid not null references public.orders (id) on delete cascade,
  created_at timestamptz not null default now()
);
create index ai_conversations_order_id_idx on public.ai_conversations (order_id);

create table public.ai_messages (
  id              uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.ai_conversations (id) on delete cascade,
  role            text not null check (role in ('user', 'assistant', 'tool')),
  content         jsonb not null,
  created_at      timestamptz not null default now()
);
create index ai_messages_conversation_id_idx on public.ai_messages (conversation_id, created_at);

create table public.ai_change_proposals (
  id                 uuid primary key default gen_random_uuid(),
  order_id           uuid not null references public.orders (id) on delete cascade,
  conversation_id    uuid references public.ai_conversations (id) on delete set null,
  base_order_version int not null,
  changes            jsonb not null,
  price_before       numeric(10,2) not null,
  price_after        numeric(10,2) not null,
  status             public.proposal_status not null default 'pending',
  created_at         timestamptz not null default now(),
  decided_at         timestamptz,
  executed_at        timestamptz
);
create index ai_change_proposals_order_id_idx        on public.ai_change_proposals (order_id);
create index ai_change_proposals_conversation_id_idx on public.ai_change_proposals (conversation_id);
-- At most one pending proposal per order.
create unique index ai_change_proposals_one_pending_per_order
  on public.ai_change_proposals (order_id) where status = 'pending';

-- ---------------------------------------------------------------- updated_at triggers
create trigger customers_set_updated_at before update on public.customers
  for each row execute function private.set_updated_at();
create trigger events_set_updated_at before update on public.events
  for each row execute function private.set_updated_at();
create trigger dishes_set_updated_at before update on public.dishes
  for each row execute function private.set_updated_at();
create trigger orders_set_updated_at before update on public.orders
  for each row execute function private.set_updated_at();

-- ---------------------------------------------------------------- RLS (deny-all for Data API)
alter table public.customers           enable row level security;
alter table public.events              enable row level security;
alter table public.dish_categories     enable row level security;
alter table public.dishes              enable row level security;
alter table public.dish_dietary        enable row level security;
alter table public.allergens           enable row level security;
alter table public.dish_allergens      enable row level security;
alter table public.delivery_zones      enable row level security;
alter table public.time_slots          enable row level security;
alter table public.blocked_dates       enable row level security;
alter table public.orders              enable row level security;
alter table public.order_items         enable row level security;
alter table public.ai_conversations    enable row level security;
alter table public.ai_messages         enable row level security;
alter table public.ai_change_proposals enable row level security;
