-- Initial schema, per docs/DATABASE_SCHEMA.md (Draft v0.1).
-- Access model: only the FastAPI backend talks to the database (direct connection / service role).
-- RLS is enabled on every table with no policies, so the public Data API (anon/authenticated) sees nothing.

-- Enums
create type pricing_unit as enum ('per_guest', 'per_tray', 'per_weight', 'per_item');
create type kashrut_class as enum ('meat', 'dairy', 'pareve');
create type fulfillment_type as enum ('pickup', 'delivery');
create type order_status as enum ('draft', 'pending_approval', 'approved', 'rejected');
create type proposal_status as enum ('pending', 'approved', 'rejected', 'expired', 'failed');
create type allergen_status as enum ('contains', 'free', 'unknown');

create table customers (
  id           uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique,  -- FK to auth.users once accounts are decided (OPEN #1)
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
  check (adults + children > 0)
);
create index idx_events_customer on events(customer_id);

create table dish_categories (
  id         uuid primary key default gen_random_uuid(),
  name       text not null unique,
  sort_order int not null default 0,
  is_active  boolean not null default true
);

create table dishes (
  id           uuid primary key default gen_random_uuid(),
  category_id  uuid not null references dish_categories(id),
  name         text not null,
  description  text,
  image_path   text,  -- object path inside the dish-images storage bucket
  pricing_unit pricing_unit not null,
  unit_price   numeric(10,2) not null check (unit_price >= 0),
  unit_label   text,
  currency     char(3) not null default 'ILS',
  min_quantity numeric(10,2),
  is_available boolean not null default true,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index idx_dishes_category on dishes(category_id);

-- Null means unknown, never "no".
create table dish_dietary (
  dish_id       uuid primary key references dishes(id) on delete cascade,
  kashrut_class kashrut_class,
  is_vegetarian boolean,
  is_vegan      boolean,
  verified_at   timestamptz
);

create table allergens (
  id   smallint primary key,
  name text not null unique
);

-- A missing row means unknown.
create table dish_allergens (
  dish_id     uuid not null references dishes(id) on delete cascade,
  allergen_id smallint not null references allergens(id),
  status      allergen_status not null,
  primary key (dish_id, allergen_id)
);
create index idx_dish_allergens_allergen on dish_allergens(allergen_id);

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
  capacity         int,
  is_active        boolean not null default true,
  check (end_time > start_time)
);

create table blocked_dates (
  id     uuid primary key default gen_random_uuid(),
  date   date not null unique,
  reason text
);

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
  subtotal         numeric(10,2),
  delivery_fee     numeric(10,2),
  total            numeric(10,2),
  submitted_at     timestamptz,
  decided_at       timestamptz,
  decision_note    text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  check (fulfillment_type <> 'delivery' or delivery_address is not null)
);
create index idx_orders_customer on orders(customer_id);
create index idx_orders_status on orders(status);
create index idx_orders_delivery_zone on orders(delivery_zone_id);

create table order_items (
  id                    uuid primary key default gen_random_uuid(),
  order_id              uuid not null references orders(id) on delete cascade,
  dish_id               uuid not null references dishes(id),
  quantity              numeric(10,2) not null check (quantity > 0),
  snapshot_name         text,
  snapshot_pricing_unit pricing_unit,
  snapshot_unit_price   numeric(10,2),
  snapshot_line_total   numeric(10,2),
  unique (order_id, dish_id)
);
create index idx_order_items_dish on order_items(dish_id);

create table ai_conversations (
  id         uuid primary key default gen_random_uuid(),
  order_id   uuid not null references orders(id) on delete cascade,
  created_at timestamptz not null default now()
);
create index idx_ai_conversations_order on ai_conversations(order_id);

create table ai_messages (
  id              uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references ai_conversations(id) on delete cascade,
  role            text not null check (role in ('user', 'assistant', 'tool')),
  content         jsonb not null,
  created_at      timestamptz not null default now()
);
create index idx_ai_messages_conversation on ai_messages(conversation_id);

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
create index idx_ai_change_proposals_order on ai_change_proposals(order_id);
create index idx_ai_change_proposals_conversation on ai_change_proposals(conversation_id);
create unique index uq_one_pending_proposal on ai_change_proposals(order_id) where status = 'pending';

-- RLS on every table, no policies: deny all through the Data API.
alter table customers           enable row level security;
alter table events              enable row level security;
alter table dish_categories     enable row level security;
alter table dishes              enable row level security;
alter table dish_dietary        enable row level security;
alter table allergens           enable row level security;
alter table dish_allergens      enable row level security;
alter table delivery_zones      enable row level security;
alter table time_slots          enable row level security;
alter table blocked_dates       enable row level security;
alter table orders              enable row level security;
alter table order_items         enable row level security;
alter table ai_conversations    enable row level security;
alter table ai_messages         enable row level security;
alter table ai_change_proposals enable row level security;

-- Catering photos. Public bucket: anyone can view an image by URL;
-- uploads go through the backend with the service role (no upload policies for anon/authenticated).
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('dish-images', 'dish-images', true, 5242880, array['image/jpeg', 'image/png', 'image/webp']);
