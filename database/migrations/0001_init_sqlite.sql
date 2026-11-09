-- 0001_init_sqlite.sql — core ordering schema for local development (SQLite >= 3.37).
-- Mirrors docs/DATABASE_SCHEMA.md (Postgres draft) so a later move to Supabase keeps the same shape.
-- Conventions:
--   * ids are UUID strings; money is INTEGER agorot (1 ILS = 100); times are ISO-8601 UTC text.
--   * nullable 0/1 flags: NULL means UNKNOWN and must never be shown as "no" / "free".
--   * every connection must run PRAGMA foreign_keys = ON (see backend/app/core/db.py).
-- Idempotent: safe to run on an existing database.

CREATE TABLE IF NOT EXISTS customers (
    id          TEXT PRIMARY KEY,
    full_name   TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    email       TEXT UNIQUE CHECK (email IS NULL OR (email = lower(email) AND email LIKE '%_@_%')),
    phone       TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

CREATE TABLE IF NOT EXISTS events (
    id                 TEXT PRIMARY KEY,
    customer_id        TEXT NOT NULL REFERENCES customers (id),
    event_type         TEXT NOT NULL,
    event_date         TEXT NOT NULL CHECK (date(event_date) IS event_date),
    adults             INTEGER NOT NULL DEFAULT 0 CHECK (adults >= 0),
    children           INTEGER NOT NULL DEFAULT 0 CHECK (children >= 0),
    vegetarian_guests  INTEGER NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
    vegan_guests       INTEGER NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),
    restricted_guests  INTEGER NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),
    dietary_notes      TEXT,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (adults + children > 0)
) STRICT;
CREATE INDEX IF NOT EXISTS ix_events_customer ON events (customer_id);
CREATE INDEX IF NOT EXISTS ix_events_date ON events (event_date);

CREATE TABLE IF NOT EXISTS dish_categories (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

CREATE TABLE IF NOT EXISTS dishes (
    id                 TEXT PRIMARY KEY,
    category_id        TEXT NOT NULL REFERENCES dish_categories (id),
    name               TEXT NOT NULL,
    description        TEXT,
    image_path         TEXT,
    pricing_unit       TEXT NOT NULL
                       CHECK (pricing_unit IN ('per_guest', 'per_tray', 'per_weight', 'per_item')),
    unit_price_agorot  INTEGER NOT NULL CHECK (unit_price_agorot >= 0),
    unit_label         TEXT,
    currency           TEXT NOT NULL DEFAULT 'ILS' CHECK (length(currency) = 3),
    min_quantity       REAL CHECK (min_quantity IS NULL OR min_quantity > 0),
    quantity_step      REAL CHECK (quantity_step IS NULL OR quantity_step > 0),
    per_guest_ratio    REAL CHECK (per_guest_ratio IS NULL OR per_guest_ratio > 0),
    kashrut_class      TEXT CHECK (kashrut_class IN ('meat', 'dairy', 'pareve')),
    is_vegetarian      INTEGER CHECK (is_vegetarian IN (0, 1)),
    is_vegan           INTEGER CHECK (is_vegan IN (0, 1)),
    sort_order         INTEGER NOT NULL DEFAULT 0,
    is_available       INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0, 1)),
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (is_vegan IS NOT 1 OR is_vegetarian IS NOT 0)
) STRICT;
CREATE INDEX IF NOT EXISTS ix_dishes_category ON dishes (category_id);

CREATE TABLE IF NOT EXISTS allergens (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
) STRICT;

-- A missing (dish, allergen) row means UNKNOWN, never "free".
CREATE TABLE IF NOT EXISTS dish_allergens (
    dish_id      TEXT NOT NULL REFERENCES dishes (id) ON DELETE CASCADE,
    allergen_id  INTEGER NOT NULL REFERENCES allergens (id),
    status       TEXT NOT NULL CHECK (status IN ('contains', 'free', 'unknown')),
    PRIMARY KEY (dish_id, allergen_id)
) STRICT;

CREATE TABLE IF NOT EXISTS orders (
    id                   TEXT PRIMARY KEY,
    order_number         INTEGER UNIQUE,
    customer_id          TEXT NOT NULL REFERENCES customers (id),
    event_id             TEXT NOT NULL UNIQUE REFERENCES events (id),
    status               TEXT NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected', 'cancelled')),
    version              INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    fulfillment_type     TEXT NOT NULL CHECK (fulfillment_type IN ('pickup', 'delivery')),
    requested_date       TEXT CHECK (requested_date IS NULL OR date(requested_date) IS requested_date),
    requested_slot       TEXT,
    delivery_city        TEXT,
    delivery_address     TEXT,
    subtotal_agorot      INTEGER CHECK (subtotal_agorot >= 0),
    delivery_fee_agorot  INTEGER CHECK (delivery_fee_agorot >= 0),
    total_agorot         INTEGER CHECK (total_agorot >= 0),
    customer_notes       TEXT,
    decision_note        TEXT,
    submitted_at         TEXT,
    decided_at           TEXT,
    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (fulfillment_type <> 'delivery'
           OR (delivery_address IS NOT NULL AND length(trim(delivery_address)) > 0))
) STRICT;
CREATE INDEX IF NOT EXISTS ix_orders_status ON orders (status);
CREATE INDEX IF NOT EXISTS ix_orders_customer ON orders (customer_id);

CREATE TABLE IF NOT EXISTS order_items (
    id                          TEXT PRIMARY KEY,
    order_id                    TEXT NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    dish_id                     TEXT NOT NULL REFERENCES dishes (id),
    quantity                    REAL NOT NULL CHECK (quantity > 0),
    -- Price snapshot: filled on submission; authoritative once the order leaves 'draft'.
    snapshot_name               TEXT,
    snapshot_pricing_unit       TEXT CHECK (snapshot_pricing_unit IS NULL OR snapshot_pricing_unit
                                    IN ('per_guest', 'per_tray', 'per_weight', 'per_item')),
    snapshot_unit_price_agorot  INTEGER CHECK (snapshot_unit_price_agorot >= 0),
    snapshot_line_total_agorot  INTEGER CHECK (snapshot_line_total_agorot >= 0),
    created_at                  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at                  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (order_id, dish_id)
) STRICT;

CREATE TABLE IF NOT EXISTS order_status_history (
    id           INTEGER PRIMARY KEY,
    order_id     TEXT NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    from_status  TEXT,
    to_status    TEXT NOT NULL,
    changed_by   TEXT NOT NULL CHECK (changed_by IN ('customer', 'owner', 'system')),
    note         TEXT,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;
CREATE INDEX IF NOT EXISTS ix_status_history_order ON order_status_history (order_id);

-- Human-friendly order numbers (1001, 1002, ...) when the app doesn't set one.
CREATE TRIGGER IF NOT EXISTS trg_orders_number AFTER INSERT ON orders
WHEN NEW.order_number IS NULL
BEGIN
    UPDATE orders
    SET order_number = (SELECT coalesce(max(order_number), 1000) + 1 FROM orders)
    WHERE id = NEW.id;
END;

-- Audit trail: record every status change automatically.
CREATE TRIGGER IF NOT EXISTS trg_orders_status_history AFTER UPDATE OF status ON orders
WHEN NEW.status IS NOT OLD.status
BEGIN
    INSERT INTO order_status_history (order_id, from_status, to_status, changed_by)
    VALUES (NEW.id, OLD.status, NEW.status, 'system');
END;

-- Keep updated_at current. The WHEN guard skips updates that already set updated_at.
CREATE TRIGGER IF NOT EXISTS trg_customers_updated AFTER UPDATE ON customers
WHEN NEW.updated_at IS OLD.updated_at
BEGIN UPDATE customers SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id; END;

CREATE TRIGGER IF NOT EXISTS trg_events_updated AFTER UPDATE ON events
WHEN NEW.updated_at IS OLD.updated_at
BEGIN UPDATE events SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id; END;

CREATE TRIGGER IF NOT EXISTS trg_dish_categories_updated AFTER UPDATE ON dish_categories
WHEN NEW.updated_at IS OLD.updated_at
BEGIN UPDATE dish_categories SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id; END;

CREATE TRIGGER IF NOT EXISTS trg_dishes_updated AFTER UPDATE ON dishes
WHEN NEW.updated_at IS OLD.updated_at
BEGIN UPDATE dishes SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id; END;

CREATE TRIGGER IF NOT EXISTS trg_orders_updated AFTER UPDATE ON orders
WHEN NEW.updated_at IS OLD.updated_at
BEGIN UPDATE orders SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id; END;

CREATE TRIGGER IF NOT EXISTS trg_order_items_updated AFTER UPDATE ON order_items
WHEN NEW.updated_at IS OLD.updated_at
BEGIN UPDATE order_items SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id; END;
