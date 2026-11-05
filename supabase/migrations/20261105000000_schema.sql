-- The schema on Supabase Postgres, ported from database/migrations/20261102000000_sqlite_schema.sql.
-- See docs/DATABASE_SCHEMA.md and ADR 0005.
-- Composite foreign keys on (caterer_id, ...) make cross-caterer references
-- impossible at the database level, even if application code has a bug.

create type pricing_unit as enum ('per_guest', 'per_tray', 'per_weight', 'per_item');
create type kashrut_class as enum ('meat', 'dairy', 'pareve');
create type fulfillment_type as enum ('pickup', 'delivery');
create type order_status as enum ('draft', 'pending_approval', 'approved', 'rejected');
create type proposal_status as enum ('pending', 'approved', 'rejected', 'expired', 'failed');
create type allergen_status as enum ('contains', 'free', 'unknown');
create type kashrut_mixing_rule as enum ('block', 'warn');
create type category_type as enum ('salad', 'main', 'side', 'dessert', 'drink', 'other');

create table caterers (
    id uuid primary key default gen_random_uuid(),
    slug text not null unique check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    name text not null,
    logo_path text,
    brand_color text check (brand_color ~ '^#[0-9a-fA-F]{6}$'),
    contact_phone text,
    -- Where a caterer hears about new orders. Null means no email is sent (OPEN_DECISIONS #13).
    notification_email text,
    kashrut_status text,
    kashrut_certificate_path text,
    kashrut_mixing_rule kashrut_mixing_rule not null default 'warn',
    currency char(3) not null default 'ILS',
    ai_monthly_message_limit int check (ai_monthly_message_limit >= 0),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table caterer_users (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete cascade,
    auth_user_id uuid not null unique references auth.users (id) on delete cascade,
    created_at timestamptz not null default now()
);
create index caterer_users_caterer_id_idx on caterer_users (caterer_id);

create table customers (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete restrict,
    full_name text not null,
    phone text not null,
    email text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (caterer_id, id)
);

create table events (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete restrict,
    customer_id uuid not null,
    event_type text not null,
    event_date date not null,
    adults int not null check (adults >= 0),
    children int not null check (children >= 0),
    vegetarian_guests int not null default 0 check (vegetarian_guests >= 0),
    vegan_guests int not null default 0 check (vegan_guests >= 0),
    restricted_guests int not null default 0 check (restricted_guests >= 0),
    dietary_notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (adults + children > 0),
    unique (caterer_id, id),
    foreign key (caterer_id, customer_id) references customers (caterer_id, id)
);
create index events_customer_idx on events (caterer_id, customer_id);

create table dish_categories (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete cascade,
    name text not null,
    category_type category_type not null default 'other',
    sort_order int not null default 0,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (caterer_id, name),
    unique (caterer_id, id)
);

create table dishes (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete cascade,
    category_id uuid not null,
    name text not null,
    description text,
    image_path text,
    pricing_unit pricing_unit not null,
    unit_price numeric(10, 2) not null check (unit_price >= 0),
    unit_label text,
    -- How many portions one tray, item, or weight unit gives. Null = no recommendation.
    servings_per_unit numeric(10, 2) check (servings_per_unit > 0),
    calories_per_portion int check (calories_per_portion >= 0),
    portion_description text,
    min_quantity numeric(10, 2) check (min_quantity > 0),
    is_available boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (caterer_id, id),
    foreign key (caterer_id, category_id) references dish_categories (caterer_id, id)
);
create index dishes_category_idx on dishes (caterer_id, category_id);

-- Null fields mean unknown, never "no".
create table dish_dietary (
    dish_id uuid primary key references dishes (id) on delete cascade,
    kashrut_class kashrut_class,
    is_vegetarian boolean,
    is_vegan boolean,
    verified_at timestamptz
);

-- Shared by every caterer.
create table allergens (
    id smallint primary key generated always as identity,
    name text not null unique
);

-- A missing row means unknown.
create table dish_allergens (
    dish_id uuid not null references dishes (id) on delete cascade,
    allergen_id smallint not null references allergens (id),
    status allergen_status not null,
    primary key (dish_id, allergen_id)
);
create index dish_allergens_allergen_idx on dish_allergens (allergen_id);

create table delivery_zones (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete cascade,
    name text not null,
    fee numeric(10, 2) not null check (fee >= 0),
    definition jsonb not null,
    is_active boolean not null default true,
    unique (caterer_id, name),
    unique (caterer_id, id)
);

create table time_slots (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete cascade,
    fulfillment_type fulfillment_type not null,
    weekday smallint check (weekday between 0 and 6),
    start_time time not null,
    end_time time not null,
    capacity int check (capacity >= 0),
    is_active boolean not null default true,
    check (end_time > start_time),
    unique (caterer_id, id)
);
create index time_slots_caterer_id_idx on time_slots (caterer_id);

create table blocked_dates (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete cascade,
    date date not null,
    reason text,
    unique (caterer_id, date)
);

-- A null caterer_id is a platform default; a caterer row overrides it.
create table quantity_rules (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid references caterers (id) on delete cascade,
    category_type category_type not null,
    portions_per_adult numeric(5, 2) not null check (portions_per_adult >= 0),
    portions_per_child numeric(5, 2) not null check (portions_per_child >= 0)
);
create unique index quantity_rules_platform_idx
    on quantity_rules (category_type) where caterer_id is null;
create unique index quantity_rules_caterer_idx
    on quantity_rules (caterer_id, category_type) where caterer_id is not null;

create table orders (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete restrict,
    access_token_hash text not null unique,
    customer_id uuid not null,
    event_id uuid not null unique,
    status order_status not null default 'draft',
    version int not null default 1,
    fulfillment_type fulfillment_type not null,
    requested_at timestamptz not null,
    time_slot_id uuid,
    delivery_city text,
    delivery_address text,
    delivery_zone_id uuid,
    subtotal numeric(10, 2),
    delivery_fee numeric(10, 2),
    total numeric(10, 2),
    kashrut_warning_acknowledged boolean not null default false,
    submitted_at timestamptz,
    decided_at timestamptz,
    decision_note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (fulfillment_type <> 'delivery' or delivery_address is not null),
    unique (caterer_id, id),
    foreign key (caterer_id, customer_id) references customers (caterer_id, id),
    foreign key (caterer_id, event_id) references events (caterer_id, id),
    foreign key (caterer_id, delivery_zone_id) references delivery_zones (caterer_id, id),
    foreign key (caterer_id, time_slot_id) references time_slots (caterer_id, id)
);
create index orders_caterer_status_idx on orders (caterer_id, status);
create index orders_customer_idx on orders (caterer_id, customer_id);
create index orders_time_slot_idx on orders (caterer_id, time_slot_id);
create index orders_zone_idx on orders (caterer_id, delivery_zone_id);

create table order_items (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null,
    order_id uuid not null,
    dish_id uuid not null,
    quantity numeric(10, 2) not null check (quantity > 0),
    -- Frozen when the order is submitted, so menu changes don't rewrite old quotes.
    snapshot_name text,
    snapshot_pricing_unit pricing_unit,
    snapshot_unit_price numeric(10, 2),
    snapshot_line_total numeric(10, 2),
    unique (order_id, dish_id),
    foreign key (caterer_id, order_id) references orders (caterer_id, id) on delete cascade,
    foreign key (caterer_id, dish_id) references dishes (caterer_id, id)
);
create index order_items_dish_idx on order_items (caterer_id, dish_id);

create table ai_conversations (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete cascade,
    order_id uuid not null unique,
    created_at timestamptz not null default now(),
    unique (order_id, id),
    unique (caterer_id, id),
    foreign key (caterer_id, order_id) references orders (caterer_id, id) on delete cascade
);

create table ai_messages (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete cascade,
    conversation_id uuid not null,
    role text not null check (role in ('user', 'assistant', 'tool')),
    content jsonb not null,
    created_at timestamptz not null default now(),
    foreign key (caterer_id, conversation_id)
        references ai_conversations (caterer_id, id) on delete cascade
);
create index ai_messages_conversation_idx on ai_messages (conversation_id, created_at);

create table ai_change_proposals (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid not null references caterers (id) on delete cascade,
    order_id uuid not null,
    conversation_id uuid,
    base_order_version int not null,
    changes jsonb not null,
    rationale text not null,
    price_before numeric(10, 2) not null,
    price_after numeric(10, 2) not null,
    status proposal_status not null default 'pending',
    created_at timestamptz not null default now(),
    decided_at timestamptz,
    executed_at timestamptz,
    foreign key (caterer_id, order_id) references orders (caterer_id, id) on delete cascade,
    foreign key (order_id, conversation_id) references ai_conversations (order_id, id)
);
create unique index ai_change_proposals_one_pending_idx
    on ai_change_proposals (order_id) where status = 'pending';

-- Monthly AI messages per caterer (OPEN_DECISIONS #16).
create table ai_usage (
    caterer_id uuid not null references caterers (id) on delete cascade,
    month date not null,
    message_count int not null default 0,
    primary key (caterer_id, month)
);

-- Shared allergen list. Draft pending OPEN_DECISIONS #8.
insert into allergens (name) values
    ('גלוטן'), ('חלב'), ('ביצים'), ('בוטנים'), ('אגוזים'), ('סויה'), ('דגים'),
    ('רכיכות וסרטנים'), ('שומשום'), ('סלרי'), ('חרדל'), ('גופרית'), ('תורמוס');

-- Draft values, unverified until a real caterer reviews them (OPEN_DECISIONS #3).
insert into quantity_rules (category_type, portions_per_adult, portions_per_child) values
    ('salad', 1.50, 1.00),
    ('main', 1.00, 0.60),
    ('side', 1.00, 0.60),
    ('dessert', 1.00, 1.00),
    ('drink', 1.00, 1.00),
    ('other', 0.00, 0.00);
