-- SQLite schema (ADR-0005). Money is integer agorot to avoid float rounding.
CREATE TABLE IF NOT EXISTS dish_categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dishes (
    id TEXT PRIMARY KEY,
    category_id TEXT NOT NULL REFERENCES dish_categories (id),
    name TEXT NOT NULL,
    description TEXT,
    price_agorot INTEGER NOT NULL CHECK (price_agorot >= 0),
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
    fee_agorot INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected')),
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    event TEXT NOT NULL, -- JSON
    subtotal_agorot INTEGER NOT NULL,
    delivery_fee_agorot INTEGER NOT NULL,
    total_agorot INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id TEXT NOT NULL REFERENCES orders (id),
    dish_id TEXT NOT NULL REFERENCES dishes (id),
    quantity REAL NOT NULL CHECK (quantity > 0),
    snapshot_name TEXT NOT NULL,
    snapshot_unit_price_agorot INTEGER NOT NULL,
    snapshot_line_total_agorot INTEGER NOT NULL,
    PRIMARY KEY (order_id, dish_id)
);
