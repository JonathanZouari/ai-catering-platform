-- SQLite schema. Conventions:
--   money = INTEGER whole shekels (ILS), no agorot; booleans = INTEGER 0/1; dates/times = ISO-8601 TEXT.
--   NULL on a dietary flag means "unknown", never "no". Catalog rows are soft-deleted (is_active/is_available)
--   because order_items reference them.
--   Schema, column names and stored codes are English. Hebrew appears only in text customers type
--   (names, address, notes) and in owner-entered catalog text (dish names, categories, cities).

CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;
-- shortcut: lead time and currency are placeholders until OPEN #5 / #17 are decided.
INSERT INTO settings (key, value) VALUES ('min_lead_days', '2'), ('currency', 'ILS');

CREATE TABLE dish_categories (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
) STRICT;

CREATE TABLE dishes (
    id                 INTEGER PRIMARY KEY,
    category_id        INTEGER NOT NULL REFERENCES dish_categories(id),
    name               TEXT NOT NULL,
    description        TEXT,
    image_path         TEXT,
    pricing_unit       TEXT NOT NULL CHECK (pricing_unit IN ('per_guest', 'per_tray', 'per_weight', 'per_item')),
    unit_price         INTEGER NOT NULL CHECK (unit_price >= 0),  -- whole ILS per pricing_unit
    quantity_step      REAL NOT NULL DEFAULT 1 CHECK (quantity_step > 0),  -- UI stepper increment (0.5 kg, 6 tartlets)
    min_quantity       REAL CHECK (min_quantity IS NULL OR min_quantity > 0),
    per_guest_qty      REAL CHECK (per_guest_qty IS NULL OR per_guest_qty > 0),  -- placeholder for quantity rules, OPEN #3
    kashrut            TEXT CHECK (kashrut IN ('meat', 'dairy', 'pareve')),
    is_vegetarian      INTEGER CHECK (is_vegetarian IN (0, 1)),
    is_vegan           INTEGER CHECK (is_vegan IN (0, 1)),
    -- 0 = allergens unknown (dish_allergens is meaningless); 1 = dish_allergens is the complete list ([] = none).
    allergens_verified INTEGER NOT NULL DEFAULT 0 CHECK (allergens_verified IN (0, 1)),
    is_available       INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0, 1)),
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT;
CREATE INDEX idx_dishes_category ON dishes(category_id);

CREATE TABLE allergens (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE dish_allergens (
    dish_id     INTEGER NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    allergen_id INTEGER NOT NULL REFERENCES allergens(id),
    PRIMARY KEY (dish_id, allergen_id)
) STRICT, WITHOUT ROWID;

CREATE TABLE delivery_zones (
    id        INTEGER PRIMARY KEY,
    city      TEXT NOT NULL UNIQUE,  -- zone = city until OPEN #19 says otherwise
    fee       INTEGER NOT NULL CHECK (fee >= 0),  -- whole ILS
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
) STRICT;

CREATE TABLE time_slots (
    id               INTEGER PRIMARY KEY,
    fulfillment_type TEXT NOT NULL CHECK (fulfillment_type IN ('pickup', 'delivery')),
    start_time       TEXT NOT NULL,  -- 'HH:MM'
    end_time         TEXT NOT NULL,
    capacity         INTEGER CHECK (capacity IS NULL OR capacity > 0),  -- OPEN #5
    is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    CHECK (end_time > start_time),
    UNIQUE (fulfillment_type, start_time, end_time)
) STRICT;

CREATE TABLE blocked_dates (
    date   TEXT PRIMARY KEY,  -- 'YYYY-MM-DD'
    reason TEXT
) STRICT, WITHOUT ROWID;

CREATE TABLE customers (
    id         INTEGER PRIMARY KEY,
    full_name  TEXT NOT NULL,
    phone      TEXT NOT NULL,
    email      TEXT,
    auth_user_id TEXT UNIQUE,  -- stays NULL while checkout is guest-only (OPEN #1)
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT;
CREATE INDEX idx_customers_phone ON customers(phone);

CREATE TABLE events (
    id                INTEGER PRIMARY KEY,
    event_type        TEXT NOT NULL CHECK (event_type IN (
                          'birthday', 'family_event', 'bar_bat_mitzvah', 'shabbat_dinner',
                          'anniversary', 'private_celebration', 'other')),
    event_date        TEXT NOT NULL,  -- 'YYYY-MM-DD'
    adults            INTEGER NOT NULL CHECK (adults >= 0),
    children          INTEGER NOT NULL DEFAULT 0 CHECK (children >= 0),
    vegetarian_guests INTEGER NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
    vegan_guests      INTEGER NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),  -- subset semantics: OPEN #4
    restricted_guests INTEGER NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),
    dietary_notes     TEXT,  -- free text typed by the customer (Hebrew); shown to the owner, never parsed
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    CHECK (adults + children > 0)
) STRICT;
CREATE INDEX idx_events_date ON events(event_date);

-- The order id is a uuid4 generated by the app and doubles as the guest access link, so it must not be
-- a sequential number. Each order has exactly one event. customer_id is NULL until the contact step.
CREATE TABLE orders (
    id               TEXT PRIMARY KEY,
    customer_id      INTEGER REFERENCES customers(id),
    event_id         INTEGER NOT NULL UNIQUE REFERENCES events(id),
    status           TEXT NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected')),
    version          INTEGER NOT NULL DEFAULT 1,  -- bump on every mutation (optimistic locking)

    fulfillment_type TEXT NOT NULL CHECK (fulfillment_type IN ('pickup', 'delivery')),
    time_slot_id     INTEGER REFERENCES time_slots(id),
    delivery_zone_id INTEGER REFERENCES delivery_zones(id),
    delivery_address TEXT,  -- typed by the customer (Hebrew)

    -- NULL while draft (prices are read live); frozen at submission. Whole ILS.
    subtotal         INTEGER CHECK (subtotal >= 0),
    delivery_fee     INTEGER CHECK (delivery_fee >= 0),
    total            INTEGER CHECK (total >= 0),

    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    submitted_at     TEXT,
    decided_at       TEXT,
    decision_note    TEXT,

    -- A submitted order must be complete.
    CHECK (status = 'draft' OR (
        customer_id IS NOT NULL AND time_slot_id IS NOT NULL
        AND total IS NOT NULL AND submitted_at IS NOT NULL)),
    CHECK (fulfillment_type = 'pickup' OR status = 'draft'
           OR (delivery_zone_id IS NOT NULL AND delivery_address IS NOT NULL))
) STRICT;
CREATE INDEX idx_orders_status ON orders(status, submitted_at);
CREATE INDEX idx_orders_customer ON orders(customer_id);

CREATE TABLE order_items (
    id                    INTEGER PRIMARY KEY,
    order_id              TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    dish_id               INTEGER NOT NULL REFERENCES dishes(id),
    quantity              REAL NOT NULL CHECK (quantity > 0),
    -- Snapshot, filled on submission: later catalog edits must not change a submitted quote.
    snapshot_name         TEXT,
    snapshot_pricing_unit TEXT,
    snapshot_unit_price   INTEGER,  -- whole ILS
    snapshot_line_total   INTEGER,  -- whole ILS; rounding rule for fractional quantities is OPEN #14
    UNIQUE (order_id, dish_id)
) STRICT;

CREATE TABLE ai_messages (
    id         INTEGER PRIMARY KEY,
    order_id   TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content    TEXT NOT NULL,  -- JSON
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT;
CREATE INDEX idx_ai_messages_order ON ai_messages(order_id, id);

CREATE TABLE ai_change_proposals (
    id                 INTEGER PRIMARY KEY,
    order_id           TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    base_order_version INTEGER NOT NULL,  -- must equal orders.version at execution
    changes            TEXT NOT NULL,     -- JSON list of typed operations
    price_before       INTEGER NOT NULL,  -- whole ILS
    price_after        INTEGER NOT NULL,
    status             TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'approved', 'rejected', 'expired', 'failed')),
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    decided_at         TEXT,
    executed_at        TEXT  -- set once: idempotency
) STRICT;
CREATE INDEX idx_proposals_order ON ai_change_proposals(order_id, status);
-- At most one open proposal per order keeps the UI simple.
CREATE UNIQUE INDEX uq_one_pending_proposal ON ai_change_proposals(order_id) WHERE status = 'pending';
