-- SQLite schema for the catering platform (lesson 15 homework).
-- A local, serverless stand-in for the Supabase/Postgres schema in docs/DATABASE_SCHEMA.md.
-- Created by: uv run python -m app.db   (from backend/)
--
-- Conventions: INTEGER PRIMARY KEY AUTOINCREMENT ids, TEXT dates (ISO 8601),
-- REAL money, 1/0/NULL booleans where NULL means "unknown" (never "no").

CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name   TEXT NOT NULL,
    phone       TEXT NOT NULL,
    email       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id        INTEGER NOT NULL,
    event_type         TEXT NOT NULL,
    event_date         TEXT NOT NULL,
    adults             INTEGER NOT NULL DEFAULT 0 CHECK (adults >= 0),
    children           INTEGER NOT NULL DEFAULT 0 CHECK (children >= 0),
    vegetarian_guests  INTEGER NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
    vegan_guests       INTEGER NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),
    dietary_notes      TEXT,
    CHECK (adults + children > 0),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS dish_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dishes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id    INTEGER NOT NULL,
    name           TEXT NOT NULL,
    description    TEXT,
    pricing_unit   TEXT NOT NULL CHECK (pricing_unit IN ('per_guest', 'per_tray', 'per_item')),
    unit_price     REAL NOT NULL CHECK (unit_price >= 0),
    kashrut        TEXT CHECK (kashrut IN ('meat', 'dairy', 'pareve')),
    is_vegetarian  INTEGER CHECK (is_vegetarian IN (0, 1)),   -- NULL = unknown
    is_vegan       INTEGER CHECK (is_vegan IN (0, 1)),        -- NULL = unknown
    is_available   INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0, 1)),
    FOREIGN KEY (category_id) REFERENCES dish_categories(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id       INTEGER NOT NULL,
    event_id          INTEGER NOT NULL UNIQUE,                 -- one event = one order
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected')),
    fulfillment_type  TEXT NOT NULL CHECK (fulfillment_type IN ('pickup', 'delivery')),
    delivery_address  TEXT,
    subtotal          REAL,
    delivery_fee      REAL,
    total             REAL,
    decision_note     TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_at      TEXT,
    CHECK (fulfillment_type = 'pickup' OR delivery_address IS NOT NULL),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (event_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id             INTEGER NOT NULL,
    dish_id              INTEGER NOT NULL,
    quantity             REAL NOT NULL CHECK (quantity > 0),
    -- Price snapshot: frozen when the order is submitted, so later menu
    -- changes never rewrite an old order.
    snapshot_name        TEXT,
    snapshot_unit_price  REAL,
    snapshot_line_total  REAL,
    UNIQUE (order_id, dish_id),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (dish_id) REFERENCES dishes(id)
);

CREATE TABLE IF NOT EXISTS allergens (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE
);

-- Many-to-many: a dish has several allergens, an allergen appears in many dishes.
-- A missing row means "unknown", which is different from 'free'.
CREATE TABLE IF NOT EXISTS dish_allergens (
    dish_id      INTEGER NOT NULL,
    allergen_id  INTEGER NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('contains', 'free')),
    PRIMARY KEY (dish_id, allergen_id),
    FOREIGN KEY (dish_id) REFERENCES dishes(id),
    FOREIGN KEY (allergen_id) REFERENCES allergens(id)
);
