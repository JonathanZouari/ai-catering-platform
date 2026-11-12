-- Initial schema for the catering platform (docs/DATABASE_SCHEMA.md v0.2).
-- Portable by design: text + CHECK instead of enum types, integer money (agorot),
-- integer quantities (thousandths of a unit), JSON instead of jsonb.
--
-- Login uses Supabase Auth: staff_users.id and customers.auth_user_id point at auth.users.
-- Row Level Security, grants, storage and realtime are set up in the next migration.

-- Step 1: tables with no foreign keys --------------------------------------

create table settings (
  id                          integer primary key check (id = 1),
  default_max_guests_per_day  integer not null check (default_max_guests_per_day > 0),
  min_lead_days               integer not null check (min_lead_days >= 0),
  vat_rate_bp                 integer not null check (vat_rate_bp >= 0),
  currency                    text    not null default 'ILS',
  updated_at                  timestamptz not null default now()
);

-- One row per staff login. The password lives in Supabase Auth, never here.
create table staff_users (
  id             uuid primary key references auth.users (id) on delete cascade,
  email          text not null unique check (email = lower(email)),
  full_name      text not null,
  is_active      boolean not null default true,
  last_login_at  timestamptz,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create table categories (
  id          uuid primary key default gen_random_uuid(),
  name        text not null unique,
  sort_order  integer not null default 0,
  is_active   boolean not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table allergens (
  id          uuid primary key default gen_random_uuid(),
  name        text not null unique,
  sort_order  integer not null default 0
);

create table delivery_zones (
  id          uuid primary key default gen_random_uuid(),
  name        text not null unique,
  fee_agorot  integer not null check (fee_agorot >= 0),
  is_active   boolean not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table time_slots (
  id           uuid primary key default gen_random_uuid(),
  fulfillment  text not null check (fulfillment in ('pickup', 'delivery')),
  weekday      integer check (weekday between 0 and 6),   -- 0 = Sunday, null = every day
  start_time   time not null,
  end_time     time not null,
  is_active    boolean not null default true,
  constraint ck_slot_order check (end_time > start_time)
);

create table calendar_overrides (
  date        date primary key,
  max_guests  integer check (max_guests >= 0),
  is_blocked  boolean not null default false,
  reason      text
);

create table customers (
  id            uuid primary key default gen_random_uuid(),
  full_name     text not null,
  phone         text not null unique check (phone ~ '^[0-9]+$'),
  email         text,
  auth_user_id  uuid unique references auth.users (id) on delete set null,  -- set when the customer has a login
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- Step 2 ---------------------------------------------------------------------

create table dishes (
  id                     uuid primary key default gen_random_uuid(),
  category_id            uuid not null references categories (id),
  name                   text not null,
  description            text,
  image_path             text,
  unit                   text not null check (unit in ('tray', '100g', 'item', 'guest')),
  unit_label             text,
  price_agorot           integer not null check (price_agorot >= 0),
  qty_per_adult_milli    integer check (qty_per_adult_milli >= 0),
  qty_per_child_milli    integer check (qty_per_child_milli >= 0),
  qty_step_milli         integer not null default 1000 check (qty_step_milli > 0),
  qty_min_milli          integer check (qty_min_milli > 0),
  kashrut                text check (kashrut in ('meat', 'dairy', 'pareve')),  -- null = unknown
  is_vegetarian          boolean,                                             -- null = unknown
  is_vegan               boolean,                                             -- null = unknown
  allergens_verified_by  uuid references staff_users (id),
  allergens_verified_at  timestamptz,
  is_available           boolean not null default true,
  sort_order             integer not null default 0,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now(),
  constraint ck_vegan_is_vegetarian check (not (is_vegan = true and is_vegetarian = false))
);
create index ix_dishes_category on dishes (category_id);
create index ix_dishes_verified_by on dishes (allergens_verified_by);

create table zone_cities (
  city     text primary key,
  zone_id  uuid not null references delivery_zones (id)
);
create index ix_zone_cities_zone on zone_cities (zone_id);

-- Step 3 ---------------------------------------------------------------------

create table dish_allergens (
  dish_id      uuid not null references dishes (id) on delete cascade,
  allergen_id  uuid not null references allergens (id),
  status       text not null check (status in ('contains', 'may_contain', 'free')),
  primary key (dish_id, allergen_id)
);
create index ix_dish_allergens_allergen on dish_allergens (allergen_id);

create table orders (
  id                   uuid primary key default gen_random_uuid(),
  customer_id          uuid not null references customers (id),
  access_token_hash    text not null unique,
  status               text not null default 'draft'
                       check (status in ('draft', 'pending_approval', 'approved', 'rejected', 'cancelled', 'completed')),
  version              integer not null default 1,
  event_type           text not null,
  event_date           date not null,
  time_slot_id         uuid references time_slots (id),
  slot_start           time,
  slot_end             time,
  adults               integer not null check (adults >= 1),
  children             integer not null default 0 check (children >= 0),
  vegetarian           integer not null default 0 check (vegetarian >= 0),
  vegan                integer not null default 0 check (vegan >= 0),
  restricted           integer not null default 0 check (restricted >= 0),
  dietary_notes        text,
  fulfillment          text not null check (fulfillment in ('pickup', 'delivery')),
  city                 text references zone_cities (city),
  delivery_address     text,
  delivery_zone_id     uuid references delivery_zones (id),
  delivery_fee_agorot  integer,
  subtotal_agorot      integer,
  total_agorot         integer,
  vat_rate_bp          integer,
  vat_agorot           integer,
  submitted_at         timestamptz,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  constraint ck_diet_within_guests check (vegetarian + vegan + restricted <= adults + children),
  constraint ck_delivery_has_address check (
    fulfillment <> 'delivery' or (city is not null and delivery_address is not null))
);
create index ix_orders_customer on orders (customer_id);
create index ix_orders_status_date on orders (status, event_date);
create index ix_orders_time_slot on orders (time_slot_id);
create index ix_orders_city on orders (city);
create index ix_orders_zone on orders (delivery_zone_id);

-- Step 4 ---------------------------------------------------------------------

create table order_items (
  id                     uuid primary key default gen_random_uuid(),
  order_id               uuid not null references orders (id) on delete cascade,
  dish_id                uuid not null references dishes (id),
  quantity_milli         integer not null check (quantity_milli > 0),
  snapshot_name          text,
  snapshot_unit          text,
  snapshot_kashrut       text,
  snapshot_price_agorot  integer,
  line_total_agorot      integer,
  constraint uq_order_dish unique (order_id, dish_id)
);
create index ix_order_items_dish on order_items (dish_id);

create table order_events (
  id             uuid primary key default gen_random_uuid(),
  order_id       uuid not null references orders (id),
  from_status    text,
  to_status      text not null,
  actor_type     text not null check (actor_type in ('customer', 'staff', 'system')),
  staff_user_id  uuid references staff_users (id),
  note           text,
  created_at     timestamptz not null default now()
);
create index ix_order_events_order on order_events (order_id, created_at);
create index ix_order_events_staff on order_events (staff_user_id);

create table ai_conversations (
  id          uuid primary key default gen_random_uuid(),
  order_id    uuid not null references orders (id),
  created_at  timestamptz not null default now()
);
create index ix_ai_conversations_order on ai_conversations (order_id);

-- Step 5 ---------------------------------------------------------------------

create table ai_messages (
  id               uuid primary key default gen_random_uuid(),
  conversation_id  uuid not null references ai_conversations (id),
  role             text not null check (role in ('user', 'assistant', 'tool')),
  content          json not null,
  created_at       timestamptz not null default now()
);
create index ix_ai_messages_conversation on ai_messages (conversation_id);

create table ai_change_proposals (
  id                   uuid primary key default gen_random_uuid(),
  order_id             uuid not null references orders (id),
  conversation_id      uuid references ai_conversations (id),
  base_order_version   integer not null,
  changes              json not null,
  price_before_agorot  integer not null,
  price_after_agorot   integer not null,
  status               text not null default 'pending'
                       check (status in ('pending', 'approved', 'rejected', 'expired', 'failed')),
  created_at           timestamptz not null default now(),
  decided_at           timestamptz,
  executed_at          timestamptz
);
create index ix_ai_proposals_order on ai_change_proposals (order_id);
create index ix_ai_proposals_conversation on ai_change_proposals (conversation_id);
-- At most one pending suggestion per order
create unique index uq_one_pending_proposal on ai_change_proposals (order_id) where status = 'pending';
