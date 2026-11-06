-- Yummai initial schema (docs/DATABASE_SCHEMA.md v0.2)

create type pricing_unit    as enum ('per_guest','per_tray','per_weight','per_item');
create type fulfillment_type as enum ('pickup','delivery');
create type order_status    as enum ('draft','pending_approval','approved','rejected');
create type proposal_status as enum ('pending','approved','rejected','expired','failed');
create type allergen_status as enum ('contains','free','unknown');
create type dish_kind       as enum ('food','drink','tools');

create function set_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

-- ---------- people ----------
create table customers (
  id uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique references auth.users(id) on delete set null,
  full_name text not null,
  email text,
  phone text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ---------- catalog ----------
create table dish_categories (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  sort_order int not null default 0,
  is_active boolean not null default true
);

create table dishes (
  id uuid primary key default gen_random_uuid(),
  category_id uuid not null references dish_categories(id),
  kind dish_kind not null default 'food',
  name text not null,
  description text,
  image_path text,
  pricing_unit pricing_unit not null,
  unit_price numeric(10,2) not null check (unit_price >= 0),
  unit_label text,
  currency char(3) not null default 'ILS',
  min_quantity numeric(10,2),
  is_available boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on dishes (category_id);

create table dish_dietary (
  dish_id uuid primary key references dishes(id) on delete cascade,
  is_vegetarian boolean,  -- null = unknown, never "no"
  is_vegan boolean,
  verified_at timestamptz
);

create table allergens (
  id smallint primary key generated always as identity,
  name text not null unique
);

create table dish_allergens (
  dish_id uuid references dishes(id) on delete cascade,
  allergen_id smallint references allergens(id),
  status allergen_status not null,
  primary key (dish_id, allergen_id)  -- missing row = unknown
);

-- whole-meal packages (priced per guest)
create table meal_packages (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,          -- med / ita / mex / tha
  name text not null,
  cuisine text not null,
  description text,
  price_per_guest numeric(10,2) not null check (price_per_guest >= 0),
  currency char(3) not null default 'ILS',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table meal_package_drinks (
  package_id uuid references meal_packages(id) on delete cascade,
  dish_id uuid references dishes(id),
  primary key (package_id, dish_id)
);

-- ---------- logistics ----------
create table event_types (
  code text primary key,
  label text not null,
  sort_order int not null default 0
);

create table delivery_zones (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  fee numeric(10,2) not null check (fee >= 0),
  definition jsonb not null default '{}',  -- shape depends on OPEN #19
  is_active boolean not null default true
);

create table time_slots (
  id uuid primary key default gen_random_uuid(),
  fulfillment_type fulfillment_type,       -- null = both
  weekday smallint check (weekday between 0 and 6),
  start_time time not null,
  end_time time not null,
  capacity int,
  is_active boolean not null default true,
  check (end_time > start_time)
);

create table blocked_dates (
  id uuid primary key default gen_random_uuid(),
  date date not null unique,
  reason text
);

-- ---------- events & orders ----------
create table events (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references customers(id),
  event_type text not null references event_types(code),
  event_date date not null,
  time_slot_id uuid references time_slots(id),
  adults int not null check (adults >= 0),
  children int not null default 0 check (children >= 0),
  omnivore_guests int not null default 0 check (omnivore_guests >= 0),
  vegetarian_guests int not null default 0 check (vegetarian_guests >= 0),
  vegan_guests int not null default 0 check (vegan_guests >= 0),
  restricted_guests int not null default 0 check (restricted_guests >= 0),
  dietary_notes text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (adults + children > 0)
);
create index on events (customer_id);
create index on events (event_date);

create table orders (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references customers(id),
  event_id uuid not null unique references events(id),
  status order_status not null default 'draft',
  version int not null default 1,
  fulfillment_type fulfillment_type not null,
  requested_at timestamptz not null,
  delivery_address text,
  delivery_zone_id uuid references delivery_zones(id),
  subtotal numeric(10,2),
  delivery_fee numeric(10,2),
  total numeric(10,2),
  notes text,
  submitted_at timestamptz,
  decided_at timestamptz,
  decision_note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (fulfillment_type <> 'delivery' or delivery_address is not null)
);
create index on orders (customer_id);
create index on orders (status);

create table order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references orders(id) on delete cascade,
  dish_id uuid references dishes(id),
  package_id uuid references meal_packages(id),
  quantity numeric(10,2) not null check (quantity > 0),
  snapshot_name text,
  snapshot_pricing_unit pricing_unit,
  snapshot_unit_price numeric(10,2),
  snapshot_line_total numeric(10,2),
  check ((dish_id is null) <> (package_id is null))  -- exactly one
);
create index on order_items (order_id);
create unique index on order_items (order_id, dish_id) where dish_id is not null;
create unique index on order_items (order_id, package_id) where package_id is not null;

-- ---------- AI ----------
create table ai_conversations (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references orders(id) on delete cascade,
  created_at timestamptz not null default now()
);
create index on ai_conversations (order_id);

create table ai_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references ai_conversations(id) on delete cascade,
  role text not null check (role in ('user','assistant','tool')),
  content jsonb not null,
  created_at timestamptz not null default now()
);
create index on ai_messages (conversation_id);

create table ai_change_proposals (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references orders(id) on delete cascade,
  conversation_id uuid references ai_conversations(id),
  base_order_version int not null,
  changes jsonb not null,
  price_before numeric(10,2) not null,
  price_after numeric(10,2) not null,
  status proposal_status not null default 'pending',
  created_at timestamptz not null default now(),
  decided_at timestamptz,
  executed_at timestamptz
);
create unique index on ai_change_proposals (order_id) where status = 'pending';

-- ---------- updated_at triggers ----------
do $$ declare t text; begin
  foreach t in array array['customers','dishes','meal_packages','events','orders'] loop
    execute format('create trigger %I before update on %I for each row execute function set_updated_at()', t||'_updated', t);
  end loop;
end $$;

-- ---------- RLS ----------
do $$ declare t text; begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table %I enable row level security', t);
  end loop;
end $$;

-- public read: catalog & logistics only. Everything else goes through the backend (service role bypasses RLS).
create policy public_read on dish_categories    for select using (is_active);
create policy public_read on dishes             for select using (is_available);
create policy public_read on dish_dietary       for select using (true);
create policy public_read on allergens          for select using (true);
create policy public_read on dish_allergens     for select using (true);
create policy public_read on meal_packages      for select using (is_active);
create policy public_read on meal_package_drinks for select using (true);
create policy public_read on event_types        for select using (true);
create policy public_read on delivery_zones     for select using (is_active);
create policy public_read on time_slots         for select using (is_active);

-- logged-in customers see only their own rows
create policy own_row on customers for select using (auth_user_id = auth.uid());
create policy own_row on events    for select using (customer_id in (select id from customers where auth_user_id = auth.uid()));
create policy own_row on orders    for select using (customer_id in (select id from customers where auth_user_id = auth.uid()));
create policy own_row on order_items for select using (order_id in (select id from orders where customer_id in (select id from customers where auth_user_id = auth.uid())));
