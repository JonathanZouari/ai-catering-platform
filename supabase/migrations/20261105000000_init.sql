-- Postgres port of backend/app/db/schema.sql (feat/sqlite-db). Money = integer agorot.
-- NULL in dietary/allergen columns means "unknown", never "no".

create table customers (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  email text,
  phone text,
  created_at timestamptz not null default now()
);

create table events (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references customers(id),
  event_type text not null,
  event_date date not null,
  adults integer not null check (adults >= 0),
  children integer not null check (children >= 0),
  vegetarian_guests integer not null default 0 check (vegetarian_guests >= 0),
  vegan_guests integer not null default 0 check (vegan_guests >= 0),
  restricted_guests integer not null default 0 check (restricted_guests >= 0),
  dietary_notes text,
  check (adults + children > 0)
);

create table dish_categories (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  sort_order integer not null default 0,
  is_active boolean not null default true
);

create table dishes (
  id uuid primary key default gen_random_uuid(),
  category_id uuid not null references dish_categories(id),
  name text not null,
  description text,
  image_path text,
  pricing_unit text not null check (pricing_unit in ('per_guest','per_tray','per_weight','per_item')),
  unit_price integer not null check (unit_price >= 0),
  unit_label text,
  min_quantity numeric,
  is_available boolean not null default true,
  created_at timestamptz not null default now()
);
create index idx_dishes_category on dishes(category_id);

create table dish_dietary (
  dish_id uuid primary key references dishes(id) on delete cascade,
  kashrut_class text check (kashrut_class in ('meat','dairy','pareve')),
  is_vegetarian boolean,
  is_vegan boolean,
  verified_at timestamptz
);

create table allergens (
  id smallint primary key,
  name text not null unique
);

-- Missing row = unknown.
create table dish_allergens (
  dish_id uuid not null references dishes(id) on delete cascade,
  allergen_id smallint not null references allergens(id),
  status text not null check (status in ('contains','free')),
  primary key (dish_id, allergen_id)
);

create table delivery_zones (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  fee integer not null check (fee >= 0),
  definition jsonb not null,
  is_active boolean not null default true
);

create table time_slots (
  id uuid primary key default gen_random_uuid(),
  fulfillment_type text not null check (fulfillment_type in ('pickup','delivery')),
  weekday smallint check (weekday between 0 and 6),
  start_time time not null,
  end_time time not null,
  capacity integer,
  is_active boolean not null default true,
  check (end_time > start_time)
);

create table blocked_dates (
  date date primary key,
  reason text
);

create table orders (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references customers(id),
  event_id uuid not null unique references events(id),
  status text not null default 'draft' check (status in ('draft','pending_approval','approved','rejected')),
  version integer not null default 1,
  fulfillment_type text not null check (fulfillment_type in ('pickup','delivery')),
  requested_at timestamptz not null,
  delivery_address text,
  delivery_zone_id uuid references delivery_zones(id),
  subtotal integer, delivery_fee integer, total integer,
  submitted_at timestamptz, decided_at timestamptz, decision_note text,
  created_at timestamptz not null default now(),
  check (fulfillment_type <> 'delivery' or delivery_address is not null)
);
create index idx_orders_customer on orders(customer_id);
create index idx_orders_status on orders(status);

-- snapshot_* are filled on submission and become authoritative then.
create table order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references orders(id) on delete cascade,
  dish_id uuid not null references dishes(id),
  quantity numeric not null check (quantity > 0),
  snapshot_name text,
  snapshot_pricing_unit text,
  snapshot_unit_price integer,
  snapshot_line_total integer,
  unique (order_id, dish_id)
);

create table ai_conversations (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references orders(id) on delete cascade,
  created_at timestamptz not null default now()
);
create index idx_ai_conv_order on ai_conversations(order_id);

create table ai_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references ai_conversations(id) on delete cascade,
  role text not null check (role in ('user','assistant','tool')),
  content jsonb not null,
  created_at timestamptz not null default now()
);

create table ai_change_proposals (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references orders(id) on delete cascade,
  conversation_id uuid references ai_conversations(id),
  base_order_version integer not null,
  changes jsonb not null,
  price_before integer not null,
  price_after integer not null,
  status text not null default 'pending' check (status in ('pending','approved','rejected','expired','failed')),
  created_at timestamptz not null default now(),
  decided_at timestamptz,
  executed_at timestamptz
);
-- At most one pending proposal per order.
create unique index idx_one_pending_proposal on ai_change_proposals(order_id) where status = 'pending';

-- Backend connects with a privileged role; RLS on with no policies blocks the public API (anon/authenticated).
alter table customers enable row level security;
alter table events enable row level security;
alter table dish_categories enable row level security;
alter table dishes enable row level security;
alter table dish_dietary enable row level security;
alter table allergens enable row level security;
alter table dish_allergens enable row level security;
alter table delivery_zones enable row level security;
alter table time_slots enable row level security;
alter table blocked_dates enable row level security;
alter table orders enable row level security;
alter table order_items enable row level security;
alter table ai_conversations enable row level security;
alter table ai_messages enable row level security;
alter table ai_change_proposals enable row level security;
