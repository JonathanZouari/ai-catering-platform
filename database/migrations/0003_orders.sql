-- Customers, events, orders and order items.
-- Mirrors backend/app/models/orders.py and docs/DATABASE_SCHEMA.md.
-- Not yet included: customers.auth_user_id (OPEN_DECISIONS #1), orders.delivery_zone_id (#19).
-- RLS is on with no policies: only the backend's privileged connection reads/writes (ADR 0002).

create type order_status as enum ('draft', 'pending_approval', 'approved', 'rejected');

create table customers (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  email text,
  phone text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table events (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references customers(id),
  event_type text not null,
  event_date date not null,
  adults int not null,
  children int not null default 0,
  vegetarian_guests int not null default 0, -- subset semantics: OPEN_DECISIONS #4
  vegan_guests int not null default 0,
  restricted_guests int not null default 0,
  dietary_notes text,
  constraint events_counts_non_negative check (
    adults >= 0 and children >= 0 and vegetarian_guests >= 0 and vegan_guests >= 0
    and restricted_guests >= 0
  ),
  constraint events_has_guests check (adults + children > 0)
);

create table orders (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references customers(id),
  event_id uuid not null unique references events(id),
  status order_status not null default 'draft',
  version int not null default 1,
  fulfillment_type fulfillment_type not null, -- enum from 0002
  requested_at timestamptz not null,
  delivery_address text,
  subtotal numeric(10, 2),
  delivery_fee numeric(10, 2),
  total numeric(10, 2),
  submitted_at timestamptz,
  decided_at timestamptz,
  decision_note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint orders_delivery_address check (
    fulfillment_type <> 'delivery' or delivery_address is not null
  )
);
create index orders_customer_id_idx on orders (customer_id);
create index orders_status_idx on orders (status);

-- While draft, prices are live from dishes; from submission the snapshot is authoritative.
create table order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references orders(id) on delete cascade,
  dish_id uuid not null references dishes(id),
  quantity numeric(10, 2) not null,
  snapshot_name text,
  snapshot_pricing_unit pricing_unit,
  snapshot_unit_price numeric(10, 2),
  snapshot_line_total numeric(10, 2),
  unique (order_id, dish_id),
  constraint order_items_quantity check (quantity > 0)
);
create index order_items_order_id_idx on order_items (order_id);

alter table customers enable row level security;
alter table events enable row level security;
alter table orders enable row level security;
alter table order_items enable row level security;
