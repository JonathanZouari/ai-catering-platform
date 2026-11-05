-- yumm.ai catering platform: Postgres schema for Supabase (port of database/schema.sql).
-- Differences from the SQLite proposal:
--   * admin_users / admin_sessions are replaced by Supabase Auth (auth.users). Admin = app_metadata.role = 'admin'.
--   * Money is still integer agorot. Dates/times/timestamps use native types. Ids exposed by the API stay text.
--   * Every table has RLS enabled. The customer flow (orders, tokens, AI) goes through the backend with the secret key.

-- ============================================================================
-- Helpers
-- ============================================================================

-- True only for signed-in users whose app_metadata (not user_metadata, which users can edit) says admin.
create or replace function public.is_admin()
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select coalesce((select auth.jwt()) -> 'app_metadata' ->> 'role', '') = 'admin';
$$;

-- ============================================================================
-- Business configuration
-- ============================================================================

create table public.business_settings (
  id          integer primary key check (id = 1),
  lead_days   integer not null default 2 check (lead_days >= 0),
  updated_at  timestamptz not null default now()
);
insert into public.business_settings (id) values (1);

create table public.event_types (
  id          integer generated always as identity primary key,
  name        text    not null unique,
  sort_order  integer not null default 0,
  is_active   boolean not null default true
);

create table public.delivery_zones (
  id          integer generated always as identity primary key,
  city        text    not null unique,
  fee         integer not null check (fee >= 0),
  is_active   boolean not null default true
);

create table public.time_slots (
  id           integer generated always as identity primary key,
  fulfillment  text    not null check (fulfillment in ('pickup', 'delivery')),
  start_time   time    not null,
  end_time     time    not null,
  is_active    boolean not null default true,
  unique (fulfillment, start_time, end_time),
  check (end_time > start_time)
);

create table public.blocked_dates (
  date    date primary key,
  reason  text
);

-- ============================================================================
-- Catalog
-- ============================================================================

create table public.dish_categories (
  id          integer generated always as identity primary key,
  slug        text    not null unique,
  name        text    not null unique,
  sort_order  integer not null default 0,
  is_active   boolean not null default true
);

create table public.allergens (
  id    integer generated always as identity primary key,
  name  text not null unique
);

create table public.dishes (
  id                     text primary key default gen_random_uuid()::text,
  category_id            integer not null references public.dish_categories(id),
  name                   text    not null,
  description            text,
  image_path             text,                       -- path inside the dish-images storage bucket
  pricing_unit           text    not null check (pricing_unit in ('tray', 'kg', 'item', 'guest')),
  unit_price             integer not null check (unit_price >= 0),     -- agorot per pricing_unit
  qty_per_guest          numeric check (qty_per_guest > 0),
  step                   numeric check (step > 0),
  kashrut                text    check (kashrut in ('meat', 'dairy', 'pareve')),   -- null = not provided
  is_vegetarian          boolean,                                                  -- null = unknown
  is_vegan               boolean,                                                  -- null = unknown
  allergens_verified_at  timestamptz,                -- null = allergen data unknown (never "safe")
  is_available           boolean not null default true,
  sort_order             integer not null default 0,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now(),
  check (is_vegan is not true or is_vegetarian is true)
);
create index idx_dishes_category on public.dishes (category_id, sort_order);

create table public.dish_allergens (
  dish_id      text    not null references public.dishes(id) on delete cascade,
  allergen_id  integer not null references public.allergens(id),
  primary key (dish_id, allergen_id)
);
create index idx_dish_allergens_allergen on public.dish_allergens (allergen_id);

-- ============================================================================
-- Orders
-- ============================================================================

create table public.orders (
  id                 text primary key default gen_random_uuid()::text,
  access_token_hash  text not null unique,
  status             text not null default 'draft'
                     check (status in ('draft', 'pending_approval', 'approved', 'rejected')),
  version            integer not null default 1 check (version >= 1),

  contact_name       text,
  contact_phone      text,

  event_type_id      integer not null references public.event_types(id),
  event_date         date    not null,
  adults             integer not null check (adults >= 1),
  children           integer not null default 0 check (children >= 0),
  vegetarian_guests  integer not null default 0 check (vegetarian_guests >= 0),
  vegan_guests       integer not null default 0 check (vegan_guests >= 0),
  restricted_guests  integer not null default 0 check (restricted_guests >= 0),
  dietary_notes      text,

  fulfillment        text    not null check (fulfillment in ('pickup', 'delivery')),
  slot_id            integer not null references public.time_slots(id),
  slot_start         time    not null,
  slot_end           time    not null,
  delivery_zone_id   integer references public.delivery_zones(id),
  city               text,
  address            text,

  subtotal           integer check (subtotal >= 0),
  delivery_fee       integer check (delivery_fee >= 0),
  total              integer check (total >= 0),

  submitted_at       timestamptz,
  decided_at         timestamptz,
  decided_by         uuid references auth.users(id) on delete set null,
  owner_note         text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),

  check (
    (fulfillment = 'delivery' and delivery_zone_id is not null and city is not null and address is not null)
    or (fulfillment = 'pickup' and delivery_zone_id is null and city is null and address is null)
  ),
  check (
    status = 'draft'
    or (contact_name is not null and contact_phone is not null and submitted_at is not null
        and subtotal is not null and delivery_fee is not null and total is not null)
  ),
  check (total is null or total = subtotal + delivery_fee),
  check ((status in ('approved', 'rejected')) = (decided_at is not null))
);
create index idx_orders_status     on public.orders (status, submitted_at);
create index idx_orders_event_date on public.orders (event_date);
create index idx_orders_event_type on public.orders (event_type_id);
create index idx_orders_slot       on public.orders (slot_id);
create index idx_orders_zone       on public.orders (delivery_zone_id);
create index idx_orders_decided_by on public.orders (decided_by);

create table public.order_items (
  id                     integer generated always as identity primary key,
  order_id               text    not null references public.orders(id) on delete cascade,
  dish_id                text    not null references public.dishes(id),
  quantity               numeric not null check (quantity > 0),
  snapshot_name          text,
  snapshot_pricing_unit  text    check (snapshot_pricing_unit in ('tray', 'kg', 'item', 'guest')),
  snapshot_unit_price    integer check (snapshot_unit_price >= 0),
  snapshot_line_total    integer check (snapshot_line_total >= 0),
  unique (order_id, dish_id),
  check (
    (snapshot_name is null and snapshot_pricing_unit is null and snapshot_unit_price is null and snapshot_line_total is null)
    or (snapshot_name is not null and snapshot_pricing_unit is not null and snapshot_unit_price is not null and snapshot_line_total is not null)
  )
);
create index idx_order_items_dish on public.order_items (dish_id);

create table public.order_status_events (
  id             integer generated always as identity primary key,
  order_id       text not null references public.orders(id) on delete cascade,
  from_status    text check (from_status in ('draft', 'pending_approval', 'approved', 'rejected')),
  to_status      text not null check (to_status in ('draft', 'pending_approval', 'approved', 'rejected')),
  actor          text not null check (actor in ('customer', 'owner', 'system')),
  admin_user_id  uuid references auth.users(id) on delete set null,
  note           text,
  created_at     timestamptz not null default now()
);
create index idx_status_events_order on public.order_status_events (order_id, created_at);
create index idx_status_events_admin on public.order_status_events (admin_user_id);

-- ============================================================================
-- AI assistant
-- ============================================================================

create table public.ai_messages (
  id          integer generated always as identity primary key,
  order_id    text not null references public.orders(id) on delete cascade,
  role        text not null check (role in ('user', 'assistant', 'tool')),
  content     text not null,
  created_at  timestamptz not null default now()
);
create index idx_ai_messages_order on public.ai_messages (order_id, id);

create table public.ai_proposals (
  id                  text primary key default gen_random_uuid()::text,
  order_id            text not null references public.orders(id) on delete cascade,
  message_id          integer references public.ai_messages(id) on delete set null,
  base_order_version  integer not null,
  changes             jsonb   not null,
  price_before        integer not null check (price_before >= 0),
  price_after         integer not null check (price_after >= 0),
  status              text    not null default 'pending'
                      check (status in ('pending', 'approved', 'rejected', 'expired', 'failed')),
  created_at          timestamptz not null default now(),
  decided_at          timestamptz,
  executed_at         timestamptz,
  check (executed_at is null or status = 'approved')
);
create index idx_ai_proposals_order   on public.ai_proposals (order_id, status);
create index idx_ai_proposals_message on public.ai_proposals (message_id);

-- ============================================================================
-- Row Level Security
-- ============================================================================

alter table public.business_settings   enable row level security;
alter table public.event_types         enable row level security;
alter table public.delivery_zones      enable row level security;
alter table public.time_slots          enable row level security;
alter table public.blocked_dates       enable row level security;
alter table public.dish_categories     enable row level security;
alter table public.allergens           enable row level security;
alter table public.dishes              enable row level security;
alter table public.dish_allergens      enable row level security;
alter table public.orders              enable row level security;
alter table public.order_items         enable row level security;
alter table public.order_status_events enable row level security;
alter table public.ai_messages         enable row level security;
alter table public.ai_proposals        enable row level security;

-- Public menu and configuration: anyone can read, only admins can change.
do $$
declare t text;
begin
  foreach t in array array[
    'business_settings','event_types','delivery_zones','time_slots','blocked_dates',
    'dish_categories','allergens','dishes','dish_allergens'
  ] loop
    execute format('grant select on public.%I to anon, authenticated', t);
    execute format('grant insert, update, delete on public.%I to authenticated', t);
    execute format('create policy "public read" on public.%I for select to anon, authenticated using (true)', t);
    execute format('create policy "admin insert" on public.%I for insert to authenticated with check ((select public.is_admin()))', t);
    execute format('create policy "admin update" on public.%I for update to authenticated using ((select public.is_admin())) with check ((select public.is_admin()))', t);
    execute format('create policy "admin delete" on public.%I for delete to authenticated using ((select public.is_admin()))', t);
  end loop;
end $$;

-- Orders and the AI conversation: customers reach them only through the backend (secret key, bypasses RLS).
-- Admins can read everything and decide on orders from the dashboard.
do $$
declare t text;
begin
  foreach t in array array['orders','order_items','order_status_events','ai_messages','ai_proposals'] loop
    execute format('grant select on public.%I to authenticated', t);
    execute format('create policy "admin read" on public.%I for select to authenticated using ((select public.is_admin()))', t);
  end loop;
end $$;

grant update on public.orders to authenticated;
create policy "admin decide" on public.orders for update to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));

grant insert on public.order_status_events to authenticated;
create policy "admin log" on public.order_status_events for insert to authenticated
  with check ((select public.is_admin()));

-- ============================================================================
-- Storage: dish images (public read, admin-only write)
-- ============================================================================

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('dish-images', 'dish-images', true, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do nothing;

-- Public bucket: objects are readable by URL without a SELECT policy. Admins need SELECT + INSERT + UPDATE
-- for upsert, and DELETE to remove.
create policy "admin select dish images" on storage.objects for select to authenticated
  using (bucket_id = 'dish-images' and (select public.is_admin()));
create policy "admin upload dish images" on storage.objects for insert to authenticated
  with check (bucket_id = 'dish-images' and (select public.is_admin()));
create policy "admin replace dish images" on storage.objects for update to authenticated
  using (bucket_id = 'dish-images' and (select public.is_admin()))
  with check (bucket_id = 'dish-images' and (select public.is_admin()));
create policy "admin delete dish images" on storage.objects for delete to authenticated
  using (bucket_id = 'dish-images' and (select public.is_admin()));
