-- SQLite schema (ADR-0005). Money is whole shekels (integer).
CREATE TABLE IF NOT EXISTS dish_categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dishes (
    id TEXT PRIMARY KEY,
    category_id TEXT NOT NULL REFERENCES dish_categories (id),
    name TEXT NOT NULL CHECK (length(name) > 0),
    description TEXT,
    price INTEGER NOT NULL CHECK (typeof(price) = 'integer' AND price >= 0),
    unit TEXT NOT NULL CHECK (unit IN ('tray', 'kg', 'item', 'guest')),
    per_guest REAL,
    step REAL,
    kashrut TEXT,
    is_vegetarian INTEGER,
    is_vegan INTEGER,
    -- JSON list. NULL = unknown, which must stay distinct from [] = verified none.
    allergens TEXT,
    is_available INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS delivery_zones (
    city TEXT PRIMARY KEY,
    fee INTEGER NOT NULL CHECK (typeof(fee) = 'integer' AND fee >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected')),
    customer_name TEXT NOT NULL CHECK (length(customer_name) > 0),
    customer_phone TEXT NOT NULL CHECK (
        length(customer_phone) BETWEEN 9 AND 10
        AND customer_phone GLOB '0[0-9]*'
        AND customer_phone NOT GLOB '*[^0-9]*'
    ),
    event TEXT NOT NULL, -- JSON
    subtotal INTEGER NOT NULL CHECK (typeof(subtotal) = 'integer' AND subtotal >= 0),
    delivery_fee INTEGER NOT NULL CHECK (typeof(delivery_fee) = 'integer' AND delivery_fee >= 0),
    total INTEGER NOT NULL CHECK (typeof(total) = 'integer' AND total >= 0),
    created_at TEXT NOT NULL,
    CHECK (total = subtotal + delivery_fee)
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id TEXT NOT NULL REFERENCES orders (id),
    dish_id TEXT NOT NULL REFERENCES dishes (id),
    quantity REAL NOT NULL CHECK (quantity > 0),
    snapshot_name TEXT NOT NULL CHECK (length(snapshot_name) > 0),
    snapshot_unit_price INTEGER NOT NULL CHECK (typeof(snapshot_unit_price) = 'integer' AND snapshot_unit_price >= 0),
    snapshot_line_total INTEGER NOT NULL CHECK (typeof(snapshot_line_total) = 'integer' AND snapshot_line_total >= 0),
    PRIMARY KEY (order_id, dish_id)
);
