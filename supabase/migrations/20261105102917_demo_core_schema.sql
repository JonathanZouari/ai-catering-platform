-- Demo core schema (subset of docs/DATABASE_SCHEMA.md). Not the final Phase 2 schema.
-- Access model: the FastAPI backend uses the service-role key (bypasses RLS) for all writes
-- and customer data. The public menu is the only thing readable by anon/authenticated.

create type public.pricing_unit as enum ('per_guest', 'per_tray', 'per_weight', 'per_item');
create type public.order_status as enum ('draft', 'pending_approval', 'approved', 'rejected');

create table public.dish_categories (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  sort_order int not null default 0,
  is_active boolean not null default true
);

create table public.dishes (
  id uuid primary key default gen_random_uuid(),
  category_id uuid not null references public.dish_categories (id),
  name text not null,
  description text,
  pricing_unit public.pricing_unit not null,
  unit_price numeric(10, 2) not null check (unit_price >= 0),
  is_available boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index dishes_category_id_idx on public.dishes (category_id);

create table public.customers (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  email text,
  phone text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.events (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers (id),
  event_type text not null,
  event_date date not null,
  adults int not null check (adults >= 0),
  children int not null check (children >= 0),
  dietary_notes text,
  check (adults + children > 0)
);
create index events_customer_id_idx on public.events (customer_id);

create table public.orders (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers (id),
  event_id uuid not null unique references public.events (id),
  status public.order_status not null default 'draft',
  version int not null default 1,
  total numeric(10, 2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index orders_customer_id_idx on public.orders (customer_id);
create index orders_status_idx on public.orders (status);

create table public.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders (id) on delete cascade,
  dish_id uuid not null references public.dishes (id),
  quantity numeric(10, 2) not null check (quantity > 0),
  unique (order_id, dish_id)
);
create index order_items_dish_id_idx on public.order_items (dish_id);

-- RLS on every table. No policies = no access for anon/authenticated (service role bypasses).
alter table public.dish_categories enable row level security;
alter table public.dishes enable row level security;
alter table public.customers enable row level security;
alter table public.events enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;

-- Public menu: read-only, available dishes and active categories only.
create policy "menu categories are public" on public.dish_categories
  for select to anon, authenticated using (is_active);

create policy "available dishes are public" on public.dishes
  for select to anon, authenticated using (is_available);
