-- The whole schema for SQLite (ADR 0007). See docs/DATABASE_SCHEMA.md and ADR 0005.
-- Composite foreign keys on (caterer_id, ...) make cross-caterer references
-- impossible at the database level, even if application code has a bug.
--
-- STRICT tables make SQLite enforce column types. Storage, set by models/types.py:
--   ids        32 hex characters
--   decimals   integer hundredths, so 12.50 is 1250 (money stays exact)
--   times      UTC text, 'YYYY-MM-DD HH:MM:SS.ffffff', which sorts in time order
--   booleans   0 or 1

create table caterers (
    id text primary key default (lower(hex(randomblob(16)))),
    slug text not null unique check (
        slug <> ''
        and slug not glob '*[^a-z0-9-]*'
        and slug not glob '-*'
        and slug not glob '*-'
        and slug not glob '*--*'
    ),
    name text not null,
    logo_path text,
    brand_color text check (
        brand_color glob '#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]'
    ),
    contact_phone text,
    -- Where a caterer hears about new orders. Null means no email is sent (OPEN_DECISIONS #13).
    notification_email text,
    kashrut_status text,
    kashrut_certificate_path text,
    kashrut_mixing_rule text not null default 'warn'
        check (kashrut_mixing_rule in ('block', 'warn')),
    currency text not null default 'ILS' check (length(currency) = 3),
    ai_monthly_message_limit integer check (ai_monthly_message_limit >= 0),
    is_active integer not null default 1 check (is_active in (0, 1)),
    created_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    updated_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now'))
) strict;

create table caterer_users (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null references caterers (id) on delete cascade,
    -- A Supabase Auth user. It lives in another system, so there's no foreign key.
    auth_user_id text not null unique,
    created_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now'))
) strict;
create index caterer_users_caterer_id_idx on caterer_users (caterer_id);

create table customers (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null references caterers (id) on delete restrict,
    full_name text not null,
    phone text not null,
    email text,
    created_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    updated_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    unique (caterer_id, id)
) strict;

create table events (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null references caterers (id) on delete restrict,
    customer_id text not null,
    event_type text not null,
    event_date text not null,
    adults integer not null check (adults >= 0),
    children integer not null check (children >= 0),
    vegetarian_guests integer not null default 0 check (vegetarian_guests >= 0),
    vegan_guests integer not null default 0 check (vegan_guests >= 0),
    restricted_guests integer not null default 0 check (restricted_guests >= 0),
    dietary_notes text,
    created_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    updated_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    check (adults + children > 0),
    unique (caterer_id, id),
    foreign key (caterer_id, customer_id) references customers (caterer_id, id)
) strict;

create table dish_categories (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null references caterers (id) on delete cascade,
    name text not null,
    category_type text not null default 'other'
        check (category_type in ('salad', 'main', 'side', 'dessert', 'drink', 'other')),
    sort_order integer not null default 0,
    is_active integer not null default 1 check (is_active in (0, 1)),
    created_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    updated_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    unique (caterer_id, name),
    unique (caterer_id, id)
) strict;

create table dishes (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null references caterers (id) on delete cascade,
    category_id text not null,
    name text not null,
    description text,
    image_path text,
    pricing_unit text not null
        check (pricing_unit in ('per_guest', 'per_tray', 'per_weight', 'per_item')),
    unit_price integer not null check (unit_price >= 0),
    unit_label text,
    -- How many portions one tray, item, or weight unit gives. Null = no recommendation.
    servings_per_unit integer check (servings_per_unit > 0),
    calories_per_portion integer check (calories_per_portion >= 0),
    portion_description text,
    min_quantity integer check (min_quantity > 0),
    is_available integer not null default 1 check (is_available in (0, 1)),
    created_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    updated_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    unique (caterer_id, id),
    foreign key (caterer_id, category_id) references dish_categories (caterer_id, id)
) strict;
create index dishes_category_idx on dishes (caterer_id, category_id);

create table dish_dietary (
    dish_id text primary key references dishes (id) on delete cascade,
    kashrut_class text check (kashrut_class in ('meat', 'dairy', 'pareve')),
    is_vegetarian integer check (is_vegetarian in (0, 1)),
    is_vegan integer check (is_vegan in (0, 1)),
    verified_at text
) strict;

create table allergens (
    id integer primary key autoincrement,
    name text not null unique
) strict;

create table dish_allergens (
    dish_id text not null references dishes (id) on delete cascade,
    allergen_id integer not null references allergens (id),
    status text not null check (status in ('contains', 'free', 'unknown')),
    primary key (dish_id, allergen_id)
) strict;

create table delivery_zones (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null references caterers (id) on delete cascade,
    name text not null,
    fee integer not null check (fee >= 0),
    definition text not null check (json_valid(definition)),
    is_active integer not null default 1 check (is_active in (0, 1)),
    unique (caterer_id, name),
    unique (caterer_id, id)
) strict;

create table time_slots (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null references caterers (id) on delete cascade,
    fulfillment_type text not null check (fulfillment_type in ('pickup', 'delivery')),
    weekday integer check (weekday between 0 and 6),
    start_time text not null,
    end_time text not null,
    capacity integer check (capacity >= 0),
    is_active integer not null default 1 check (is_active in (0, 1)),
    check (end_time > start_time),
    unique (caterer_id, id)
) strict;
create index time_slots_caterer_id_idx on time_slots (caterer_id);

create table blocked_dates (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null references caterers (id) on delete cascade,
    date text not null,
    reason text,
    unique (caterer_id, date)
) strict;

-- A null caterer_id is a platform default; a caterer row overrides it.
create table quantity_rules (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text references caterers (id) on delete cascade,
    category_type text not null
        check (category_type in ('salad', 'main', 'side', 'dessert', 'drink', 'other')),
    portions_per_adult integer not null check (portions_per_adult >= 0),
    portions_per_child integer not null check (portions_per_child >= 0)
) strict;
create unique index quantity_rules_platform_idx
    on quantity_rules (category_type) where caterer_id is null;
create unique index quantity_rules_caterer_idx
    on quantity_rules (caterer_id, category_type) where caterer_id is not null;

create table orders (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null references caterers (id) on delete restrict,
    access_token_hash text not null unique,
    customer_id text not null,
    event_id text not null unique,
    status text not null default 'draft'
        check (status in ('draft', 'pending_approval', 'approved', 'rejected')),
    version integer not null default 1,
    fulfillment_type text not null check (fulfillment_type in ('pickup', 'delivery')),
    requested_at text not null,
    time_slot_id text,
    delivery_city text,
    delivery_address text,
    delivery_zone_id text,
    subtotal integer,
    delivery_fee integer,
    total integer,
    kashrut_warning_acknowledged integer not null default 0
        check (kashrut_warning_acknowledged in (0, 1)),
    submitted_at text,
    decided_at text,
    decision_note text,
    created_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    updated_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    check (fulfillment_type <> 'delivery' or delivery_address is not null),
    unique (caterer_id, id),
    foreign key (caterer_id, customer_id) references customers (caterer_id, id),
    foreign key (caterer_id, event_id) references events (caterer_id, id),
    foreign key (caterer_id, delivery_zone_id) references delivery_zones (caterer_id, id),
    foreign key (caterer_id, time_slot_id) references time_slots (caterer_id, id)
) strict;
create index orders_caterer_status_idx on orders (caterer_id, status);
create index orders_customer_idx on orders (caterer_id, customer_id);
create index orders_time_slot_idx on orders (caterer_id, time_slot_id);

create table order_items (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null,
    order_id text not null,
    dish_id text not null,
    quantity integer not null check (quantity > 0),
    snapshot_name text,
    snapshot_pricing_unit text
        check (snapshot_pricing_unit in ('per_guest', 'per_tray', 'per_weight', 'per_item')),
    snapshot_unit_price integer,
    snapshot_line_total integer,
    unique (order_id, dish_id),
    foreign key (caterer_id, order_id) references orders (caterer_id, id) on delete cascade,
    foreign key (caterer_id, dish_id) references dishes (caterer_id, id)
) strict;

create table ai_conversations (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null references caterers (id) on delete cascade,
    order_id text not null unique,
    created_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    unique (order_id, id),
    unique (caterer_id, id),
    foreign key (caterer_id, order_id) references orders (caterer_id, id) on delete cascade
) strict;

create table ai_messages (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null references caterers (id) on delete cascade,
    conversation_id text not null,
    role text not null check (role in ('user', 'assistant', 'tool')),
    content text not null check (json_valid(content)),
    created_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    foreign key (caterer_id, conversation_id)
        references ai_conversations (caterer_id, id) on delete cascade
) strict;
create index ai_messages_conversation_idx on ai_messages (conversation_id, created_at);

create table ai_change_proposals (
    id text primary key default (lower(hex(randomblob(16)))),
    caterer_id text not null references caterers (id) on delete cascade,
    order_id text not null,
    conversation_id text,
    base_order_version integer not null,
    changes text not null check (json_valid(changes)),
    rationale text not null,
    price_before integer not null,
    price_after integer not null,
    status text not null default 'pending'
        check (status in ('pending', 'approved', 'rejected', 'expired', 'failed')),
    created_at text not null default (strftime('%Y-%m-%d %H:%M:%f000', 'now')),
    decided_at text,
    executed_at text,
    foreign key (caterer_id, order_id) references orders (caterer_id, id) on delete cascade,
    foreign key (order_id, conversation_id) references ai_conversations (order_id, id)
) strict;
create unique index ai_change_proposals_one_pending_idx
    on ai_change_proposals (order_id) where status = 'pending';

-- Monthly AI messages per caterer (OPEN_DECISIONS #16).
create table ai_usage (
    caterer_id text not null references caterers (id) on delete cascade,
    month text not null,
    message_count integer not null default 0,
    primary key (caterer_id, month)
) strict;

-- Shared allergen list, used by every caterer (see DATABASE_SCHEMA.md).
-- Draft list pending OPEN_DECISIONS #8.
insert into allergens (name) values
    ('גלוטן'),
    ('חלב'),
    ('ביצים'),
    ('בוטנים'),
    ('אגוזים'),
    ('סויה'),
    ('דגים'),
    ('רכיכות וסרטנים'),
    ('שומשום'),
    ('סלרי'),
    ('חרדל'),
    ('גופרית'),
    ('תורמוס');

-- Draft values in hundredths, unverified until a real caterer reviews them (OPEN_DECISIONS #3).
insert into quantity_rules (category_type, portions_per_adult, portions_per_child) values
    ('salad', 150, 100),
    ('main', 100, 60),
    ('side', 100, 60),
    ('dessert', 100, 100),
    ('drink', 100, 100),
    ('other', 0, 0);
