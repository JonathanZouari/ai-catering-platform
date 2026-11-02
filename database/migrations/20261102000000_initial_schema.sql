-- Initial schema for the AI Catering Platform (see docs/DATABASE_SCHEMA.md).
-- Conventions: uuid PKs, timestamptz audit columns, money numeric(10,2), RLS on every table.
-- RLS is enabled with NO policies: anon/authenticated roles get nothing; the backend uses the
-- service-role key. Add policies when Supabase Auth is wired in.
-- TODO(open #1): customer accounts vs guest checkout (customers.auth_user_id has no FK yet).
-- TODO(open #19): shape of delivery_zones.definition.
-- TODO(open #5): time_slots.capacity semantics.
-- TODO(open #4): vegetarian/vegan guest subset semantics (no cross-check constraint yet).

begin;

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------- enums
create type pricing_unit     as enum ('per_guest', 'per_tray', 'per_weight', 'per_item');
create type kashrut_class    as enum ('meat', 'dairy', 'pareve');
create type fulfillment_type as enum ('pickup', 'delivery');
create type order_status     as enum ('draft', 'pending_approval', 'approved', 'rejected');
create type proposal_status  as enum ('pending', 'approved', 'rejected', 'expired', 'failed');
create type allergen_status  as enum ('contains', 'free', 'unknown');

-- ---------------------------------------------------------------- helpers
create function set_updated_at() returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

-- ---------------------------------------------------------------- business settings (single row)
create table business_settings (
  id                 boolean primary key default true check (id),
  business_name      text not null,
  currency           char(3) not null default 'ILS',
  vat_rate           numeric(5,4) not null default 0 check (vat_rate >= 0),
  min_lead_time_days int not null default 0 check (min_lead_time_days >= 0),
  contact_email      text,
  contact_phone      text,
  updated_at         timestamptz not null default now()
);

-- ---------------------------------------------------------------- people
create table admin_users (
  id           uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique,
  full_name    text not null,
  email        text not null unique,
  is_active    boolean not null default true,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create table customers (
  id           uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique,
  full_name    text not null,
  email        text,
  phone        text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create table events (
  id                uuid primary key default gen_random_uuid(),
  customer_id       uuid not null references customers(id),
  event_type        text not null,
  event_date        date not null,
  adults            int not null check (adults >= 0),
  children          int not null check (children >= 0),
  vegetarian_guests int not null default 0 check (vegetarian_guests >= 0),
  vegan_guests      int not null default 0 check (vegan_guests >= 0),
  restricted_guests int not null default 0 check (restricted_guests >= 0),
  dietary_notes     text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  check (adults + children > 0)
);
create index events_customer_idx on events(customer_id);

-- ---------------------------------------------------------------- catalog
create table dish_categories (
  id         uuid primary key default gen_random_uuid(),
  name       text not null unique,
  sort_order int not null default 0,
  is_active  boolean not null default true
);

create table dishes (
  id            uuid primary key default gen_random_uuid(),
  category_id   uuid not null references dish_categories(id),
  name          text not null,
  description   text,
  image_path    text,
  pricing_unit  pricing_unit not null,
  unit_price    numeric(10,2) not null check (unit_price >= 0),
  unit_label    text,
  min_quantity  numeric(10,2) check (min_quantity is null or min_quantity > 0),
  is_available  boolean not null default true,
  deleted_at    timestamptz,                 -- soft delete: order_items keep referencing it
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index dishes_category_idx on dishes(category_id);

-- Null = not provided / unknown. Never present null as "no".
create table dish_dietary (
  dish_id       uuid primary key references dishes(id) on delete cascade,
  kashrut_class kashrut_class,
  is_vegetarian boolean,
  is_vegan      boolean,
  verified_at   timestamptz
);

create table allergens (
  id   smallint primary key generated always as identity,
  name text not null unique
);

-- Missing row = unknown.
create table dish_allergens (
  dish_id     uuid not null references dishes(id) on delete cascade,
  allergen_id smallint not null references allergens(id),
  status      allergen_status not null,
  primary key (dish_id, allergen_id)
);

create table dish_tags (
  id   uuid primary key default gen_random_uuid(),
  name text not null unique
);
create table dish_tag_links (
  dish_id uuid not null references dishes(id) on delete cascade,
  tag_id  uuid not null references dish_tags(id) on delete cascade,
  primary key (dish_id, tag_id)
);

-- Quantity rules (open #3): deliberately generic until formulas are known.
create table quantity_rules (
  id               uuid primary key default gen_random_uuid(),
  category_id      uuid not null references dish_categories(id),
  guest_basis      text not null check (guest_basis in ('adult', 'child', 'guest')),
  amount_per_guest numeric(10,3) not null check (amount_per_guest > 0),
  params           jsonb not null default '{}',
  is_active        boolean not null default true
);
create index quantity_rules_category_idx on quantity_rules(category_id);

-- ---------------------------------------------------------------- logistics
create table delivery_zones (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  fee        numeric(10,2) not null check (fee >= 0),
  definition jsonb not null,
  is_active  boolean not null default true
);

create table time_slots (
  id               uuid primary key default gen_random_uuid(),
  fulfillment_type fulfillment_type not null,
  weekday          smallint check (weekday between 0 and 6),
  start_time       time not null,
  end_time         time not null,
  capacity         int check (capacity is null or capacity > 0),
  is_active        boolean not null default true,
  check (end_time > start_time)
);

create table blocked_dates (
  id     uuid primary key default gen_random_uuid(),
  date   date not null unique,
  reason text
);

-- ---------------------------------------------------------------- orders
create table orders (
  id               uuid primary key default gen_random_uuid(),
  customer_id      uuid not null references customers(id),
  event_id         uuid not null unique references events(id),
  status           order_status not null default 'draft',
  version          int not null default 1,
  fulfillment_type fulfillment_type not null,
  requested_at     timestamptz not null,
  delivery_address text,
  delivery_zone_id uuid references delivery_zones(id),
  subtotal         numeric(10,2) check (subtotal >= 0),
  delivery_fee     numeric(10,2) check (delivery_fee >= 0),
  total            numeric(10,2) check (total >= 0),
  submitted_at     timestamptz,
  decided_at       timestamptz,
  decided_by       uuid references admin_users(id),
  decision_note    text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  check (fulfillment_type <> 'delivery' or delivery_address is not null)
);
create index orders_customer_idx on orders(customer_id);
create index orders_status_idx   on orders(status);

create table order_items (
  id                    uuid primary key default gen_random_uuid(),
  order_id              uuid not null references orders(id) on delete cascade,
  dish_id               uuid not null references dishes(id),
  quantity              numeric(10,2) not null check (quantity > 0),
  notes                 text,
  -- Price snapshot, filled on submission; authoritative once order is pending_approval.
  snapshot_name         text,
  snapshot_pricing_unit pricing_unit,
  snapshot_unit_price   numeric(10,2),
  snapshot_line_total   numeric(10,2),
  unique (order_id, dish_id)
);
create index order_items_order_idx on order_items(order_id);

create table order_status_history (
  id          uuid primary key default gen_random_uuid(),
  order_id    uuid not null references orders(id) on delete cascade,
  from_status order_status,
  to_status   order_status not null,
  actor_type  text not null check (actor_type in ('customer', 'admin', 'system')),
  actor_id    uuid,
  note        text,
  created_at  timestamptz not null default now()
);
create index order_status_history_order_idx on order_status_history(order_id);

-- ---------------------------------------------------------------- AI assistant
create table ai_conversations (
  id         uuid primary key default gen_random_uuid(),
  order_id   uuid not null references orders(id) on delete cascade,
  created_at timestamptz not null default now()
);
create index ai_conversations_order_idx on ai_conversations(order_id);

create table ai_messages (
  id              uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references ai_conversations(id) on delete cascade,
  role            text not null check (role in ('user', 'assistant', 'tool')),
  content         jsonb not null,
  created_at      timestamptz not null default now()
);
create index ai_messages_conversation_idx on ai_messages(conversation_id);

create table ai_change_proposals (
  id                 uuid primary key default gen_random_uuid(),
  order_id           uuid not null references orders(id) on delete cascade,
  conversation_id    uuid references ai_conversations(id),
  base_order_version int not null,
  changes            jsonb not null,
  price_before       numeric(10,2) not null,
  price_after        numeric(10,2) not null,
  status             proposal_status not null default 'pending',
  created_at         timestamptz not null default now(),
  decided_at         timestamptz,
  executed_at        timestamptz
);
create index ai_change_proposals_order_idx on ai_change_proposals(order_id);
create unique index ai_change_proposals_one_pending
  on ai_change_proposals(order_id) where status = 'pending';

-- ---------------------------------------------------------------- updated_at triggers
create trigger trg_business_settings_updated before update on business_settings
  for each row execute function set_updated_at();
create trigger trg_admin_users_updated before update on admin_users
  for each row execute function set_updated_at();
create trigger trg_customers_updated  before update on customers
  for each row execute function set_updated_at();
create trigger trg_events_updated     before update on events
  for each row execute function set_updated_at();
create trigger trg_dishes_updated     before update on dishes
  for each row execute function set_updated_at();
create trigger trg_orders_updated     before update on orders
  for each row execute function set_updated_at();

-- ---------------------------------------------------------------- RLS (deny by default)
alter table business_settings    enable row level security;
alter table admin_users          enable row level security;
alter table customers            enable row level security;
alter table events               enable row level security;
alter table dish_categories      enable row level security;
alter table dishes               enable row level security;
alter table dish_dietary         enable row level security;
alter table allergens            enable row level security;
alter table dish_allergens       enable row level security;
alter table dish_tags            enable row level security;
alter table dish_tag_links       enable row level security;
alter table quantity_rules       enable row level security;
alter table delivery_zones       enable row level security;
alter table time_slots           enable row level security;
alter table blocked_dates        enable row level security;
alter table orders               enable row level security;
alter table order_items          enable row level security;
alter table order_status_history enable row level security;
alter table ai_conversations     enable row level security;
alter table ai_messages          enable row level security;
alter table ai_change_proposals  enable row level security;

commit;
