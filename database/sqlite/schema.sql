-- SQLite port of docs/DATABASE_SCHEMA.md (Draft v0.1, originally PostgreSQL / Supabase).
-- Enums become CHECK constraints, uuid -> TEXT, timestamptz -> ISO-8601 TEXT, bool -> INTEGER 0/1,
-- jsonb -> TEXT (JSON). Run with foreign keys enabled.

PRAGMA foreign_keys = ON;

CREATE TABLE customers (
    id           TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    auth_user_id TEXT UNIQUE,
    full_name    TEXT NOT NULL,
    email        TEXT,
    phone        TEXT,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE events (
    id                TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    customer_id       TEXT NOT NULL REFERENCES customers(id),
    event_type        TEXT NOT NULL,
    event_date        TEXT NOT NULL,
    adults            INTEGER NOT NULL CHECK (adults >= 0),
    children          INTEGER NOT NULL CHECK (children >= 0),
    vegetarian_guests INTEGER NOT NULL CHECK (vegetarian_guests >= 0),
    vegan_guests      INTEGER NOT NULL CHECK (vegan_guests >= 0),
    restricted_guests INTEGER NOT NULL CHECK (restricted_guests >= 0),
    dietary_notes     TEXT,
    CHECK (adults + children > 0)
);
CREATE INDEX idx_events_customer_id ON events(customer_id);

CREATE TABLE dish_categories (
    id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    name       TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE dishes (
    id           TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    category_id  TEXT NOT NULL REFERENCES dish_categories(id),
    name         TEXT NOT NULL,
    description  TEXT,
    image_path   TEXT,
    pricing_unit TEXT NOT NULL CHECK (pricing_unit IN ('per_guest', 'per_tray', 'per_weight', 'per_item')),
    unit_price   NUMERIC NOT NULL CHECK (unit_price >= 0),
    unit_label   TEXT,
    currency     TEXT NOT NULL DEFAULT 'ILS' CHECK (length(currency) = 3),
    min_quantity NUMERIC,
    is_available INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0, 1)),
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_dishes_category_id ON dishes(category_id);

-- NULL means "not provided / unknown"; never present NULL as "no".
CREATE TABLE dish_dietary (
    dish_id       TEXT PRIMARY KEY REFERENCES dishes(id) ON DELETE CASCADE,
    kashrut_class TEXT CHECK (kashrut_class IN ('meat', 'dairy', 'pareve')),
    is_vegetarian INTEGER CHECK (is_vegetarian IN (0, 1)),
    is_vegan      INTEGER CHECK (is_vegan IN (0, 1)),
    verified_at   TEXT
);

CREATE TABLE allergens (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- A missing row means "unknown".
CREATE TABLE dish_allergens (
    dish_id     TEXT NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    allergen_id INTEGER NOT NULL REFERENCES allergens(id),
    status      TEXT NOT NULL CHECK (status IN ('contains', 'free', 'unknown')),
    PRIMARY KEY (dish_id, allergen_id)
);

CREATE TABLE delivery_zones (
    id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    name       TEXT NOT NULL,
    fee        NUMERIC NOT NULL CHECK (fee >= 0),
    definition TEXT NOT NULL CHECK (json_valid(definition)),
    is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE time_slots (
    id               TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    fulfillment_type TEXT NOT NULL CHECK (fulfillment_type IN ('pickup', 'delivery')),
    weekday          INTEGER CHECK (weekday BETWEEN 0 AND 6),
    start_time       TEXT NOT NULL,
    end_time         TEXT NOT NULL,
    capacity         INTEGER,
    is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    CHECK (end_time > start_time)
);

CREATE TABLE blocked_dates (
    id     TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    date   TEXT NOT NULL UNIQUE,
    reason TEXT
);

CREATE TABLE orders (
    id               TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    customer_id      TEXT NOT NULL REFERENCES customers(id),
    event_id         TEXT NOT NULL UNIQUE REFERENCES events(id),
    status           TEXT NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected')),
    version          INTEGER NOT NULL DEFAULT 1,
    fulfillment_type TEXT NOT NULL CHECK (fulfillment_type IN ('pickup', 'delivery')),
    requested_at     TEXT NOT NULL,
    delivery_address TEXT,
    delivery_zone_id TEXT REFERENCES delivery_zones(id),
    subtotal         NUMERIC,
    delivery_fee     NUMERIC,
    total            NUMERIC,
    submitted_at     TEXT,
    decided_at       TEXT,
    decision_note    TEXT,
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (fulfillment_type <> 'delivery' OR delivery_address IS NOT NULL)
);
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);

CREATE TABLE order_items (
    id                    TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    order_id              TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    dish_id               TEXT NOT NULL REFERENCES dishes(id),
    quantity              NUMERIC NOT NULL CHECK (quantity > 0),
    snapshot_name         TEXT,
    snapshot_pricing_unit TEXT CHECK (snapshot_pricing_unit IN ('per_guest', 'per_tray', 'per_weight', 'per_item')),
    snapshot_unit_price   NUMERIC,
    snapshot_line_total   NUMERIC,
    UNIQUE (order_id, dish_id)
);
CREATE INDEX idx_order_items_order_id ON order_items(order_id);

CREATE TABLE ai_conversations (
    id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    order_id   TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_ai_conversations_order_id ON ai_conversations(order_id);

CREATE TABLE ai_messages (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    conversation_id TEXT NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content         TEXT NOT NULL CHECK (json_valid(content)),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE ai_change_proposals (
    id                 TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    order_id           TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    conversation_id    TEXT REFERENCES ai_conversations(id),
    base_order_version INTEGER NOT NULL,
    changes            TEXT NOT NULL CHECK (json_valid(changes)),
    price_before       NUMERIC NOT NULL,
    price_after        NUMERIC NOT NULL,
    status             TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'approved', 'rejected', 'expired', 'failed')),
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    decided_at         TEXT,
    executed_at        TEXT
);
CREATE INDEX idx_ai_change_proposals_order_id ON ai_change_proposals(order_id);
-- At most one pending proposal per order (RECOMMENDATION in the schema doc).
CREATE UNIQUE INDEX uq_ai_change_proposals_one_pending
    ON ai_change_proposals(order_id) WHERE status = 'pending';
