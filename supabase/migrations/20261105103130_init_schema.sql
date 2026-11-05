-- Postgres port of database/migrations/0001_init.sql (SQLite).
-- Conventions: money = integer whole ILS; NULL on a dietary flag = unknown; catalog rows are soft-deleted.
-- Access: the FastAPI backend connects directly (service role / DB role, bypasses RLS). RLS is enabled on every
-- table with no policies, so anon/authenticated reach nothing through the Data API until policies are added.

create table settings (
    key   text primary key,
    value text not null
);
-- shortcut: lead time and currency are placeholders until OPEN #5 / #17 are decided.
insert into settings (key, value) values ('min_lead_days', '2'), ('currency', 'ILS');

create table dish_categories (
    id         bigint generated always as identity primary key,
    name       text not null unique,
    sort_order integer not null default 0,
    is_active  boolean not null default true
);

create table dishes (
    id                 bigint generated always as identity primary key,
    category_id        bigint not null references dish_categories(id),
    name               text not null,
    description        text,
    image_path         text,
    pricing_unit       text not null check (pricing_unit in ('per_guest', 'per_tray', 'per_weight', 'per_item')),
    unit_price         integer not null check (unit_price >= 0),            -- whole ILS per pricing_unit
    quantity_step      numeric(8,2) not null default 1 check (quantity_step > 0),
    min_quantity       numeric(8,2) check (min_quantity is null or min_quantity > 0),
    per_guest_qty      numeric(8,2) check (per_guest_qty is null or per_guest_qty > 0),  -- OPEN #3
    kashrut            text check (kashrut in ('meat', 'dairy', 'pareve')),
    is_vegetarian      boolean,
    is_vegan           boolean,
    -- false = allergens unknown (dish_allergens is meaningless); true = dish_allergens is the complete list.
    allergens_verified boolean not null default false,
    is_available       boolean not null default true,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);
create index idx_dishes_category on dishes(category_id);

create table allergens (
    id   bigint generated always as identity primary key,
    name text not null unique
);

create table dish_allergens (
    dish_id     bigint not null references dishes(id) on delete cascade,
    allergen_id bigint not null references allergens(id),
    primary key (dish_id, allergen_id)
);
create index idx_dish_allergens_allergen on dish_allergens(allergen_id);

create table delivery_zones (
    id        bigint generated always as identity primary key,
    city      text not null unique,                                          -- zone = city, OPEN #19
    fee       integer not null check (fee >= 0),
    is_active boolean not null default true
);

create table time_slots (
    id               bigint generated always as identity primary key,
    fulfillment_type text not null check (fulfillment_type in ('pickup', 'delivery')),
    start_time       time not null,
    end_time         time not null,
    capacity         integer check (capacity is null or capacity > 0),       -- OPEN #5
    is_active        boolean not null default true,
    check (end_time > start_time),
    unique (fulfillment_type, start_time, end_time)
);

create table blocked_dates (
    date   date primary key,
    reason text
);

create table customers (
    id           bigint generated always as identity primary key,
    full_name    text not null,
    phone        text not null,
    email        text,
    auth_user_id uuid unique references auth.users(id) on delete set null,   -- NULL while checkout is guest-only (OPEN #1)
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);
create index idx_customers_phone on customers(phone);

create table events (
    id                bigint generated always as identity primary key,
    event_type        text not null check (event_type in (
                          'birthday', 'family_event', 'bar_bat_mitzvah', 'shabbat_dinner',
                          'anniversary', 'private_celebration', 'other')),
    event_date        date not null,
    adults            integer not null check (adults >= 0),
    children          integer not null default 0 check (children >= 0),
    vegetarian_guests integer not null default 0 check (vegetarian_guests >= 0),
    vegan_guests      integer not null default 0 check (vegan_guests >= 0),  -- subset semantics: OPEN #4
    restricted_guests integer not null default 0 check (restricted_guests >= 0),
    dietary_notes     text,                                                  -- free text typed by the customer, never parsed
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now(),
    check (adults + children > 0)
);
create index idx_events_date on events(event_date);

-- The order id is a random uuid and doubles as the guest access link, so it must not be sequential.
create table orders (
    id               uuid primary key default gen_random_uuid(),
    customer_id      bigint references customers(id),
    event_id         bigint not null unique references events(id),
    status           text not null default 'draft'
                     check (status in ('draft', 'pending_approval', 'approved', 'rejected')),
    version          integer not null default 1,                             -- bump on every mutation (optimistic locking)

    fulfillment_type text not null check (fulfillment_type in ('pickup', 'delivery')),
    time_slot_id     bigint references time_slots(id),
    delivery_zone_id bigint references delivery_zones(id),
    delivery_address text,

    -- NULL while draft (prices are read live); frozen at submission. Whole ILS.
    subtotal         integer check (subtotal >= 0),
    delivery_fee     integer check (delivery_fee >= 0),
    total            integer check (total >= 0),

    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),
    submitted_at     timestamptz,
    decided_at       timestamptz,
    decision_note    text,

    -- A submitted order must be complete.
    check (status = 'draft' or (
        customer_id is not null and time_slot_id is not null
        and total is not null and submitted_at is not null)),
    check (fulfillment_type = 'pickup' or status = 'draft'
           or (delivery_zone_id is not null and delivery_address is not null))
);
create index idx_orders_status on orders(status, submitted_at);
create index idx_orders_customer on orders(customer_id);
create index idx_orders_time_slot on orders(time_slot_id);
create index idx_orders_delivery_zone on orders(delivery_zone_id);

create table order_items (
    id                    bigint generated always as identity primary key,
    order_id              uuid not null references orders(id) on delete cascade,
    dish_id               bigint not null references dishes(id),
    quantity              numeric(8,2) not null check (quantity > 0),
    -- Snapshot, filled on submission: later catalog edits must not change a submitted quote.
    snapshot_name         text,
    snapshot_pricing_unit text,
    snapshot_unit_price   integer,
    snapshot_line_total   integer,                                           -- rounding rule: OPEN #14
    unique (order_id, dish_id)
);
create index idx_order_items_dish on order_items(dish_id);

create table ai_messages (
    id         bigint generated always as identity primary key,
    order_id   uuid not null references orders(id) on delete cascade,
    role       text not null check (role in ('user', 'assistant', 'tool')),
    content    jsonb not null,
    created_at timestamptz not null default now()
);
create index idx_ai_messages_order on ai_messages(order_id, id);

create table ai_change_proposals (
    id                 bigint generated always as identity primary key,
    order_id           uuid not null references orders(id) on delete cascade,
    base_order_version integer not null,                                     -- must equal orders.version at execution
    changes            jsonb not null,                                       -- list of typed operations
    price_before       integer not null,
    price_after        integer not null,
    status             text not null default 'pending'
                       check (status in ('pending', 'approved', 'rejected', 'expired', 'failed')),
    created_at         timestamptz not null default now(),
    decided_at         timestamptz,
    executed_at        timestamptz                                           -- set once: idempotency
);
create index idx_proposals_order on ai_change_proposals(order_id, status);
-- At most one open proposal per order keeps the UI simple.
create unique index uq_one_pending_proposal on ai_change_proposals(order_id) where status = 'pending';

-- RLS on every table in the exposed schema; no policies yet (deny by default for anon/authenticated).
alter table settings            enable row level security;
alter table dish_categories     enable row level security;
alter table dishes              enable row level security;
alter table allergens           enable row level security;
alter table dish_allergens      enable row level security;
alter table delivery_zones      enable row level security;
alter table time_slots          enable row level security;
alter table blocked_dates       enable row level security;
alter table customers           enable row level security;
alter table events              enable row level security;
alter table orders              enable row level security;
alter table order_items         enable row level security;
alter table ai_messages         enable row level security;
alter table ai_change_proposals enable row level security;
