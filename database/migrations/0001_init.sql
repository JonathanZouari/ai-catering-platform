-- SQLite schema, first cut of docs/DATABASE_SCHEMA.md.
-- Differences from the Postgres draft, forced by SQLite:
--   * ids are INTEGER PRIMARY KEY instead of uuid
--   * enums are CHECK constraints
--   * money is INTEGER in minor units (agorot), so sums never hit float rounding
--   * timestamps are ISO-8601 TEXT in UTC
-- Not here yet: delivery zones, time slots, blocked dates and the AI tables.

CREATE TABLE dish_categories (
  id         INTEGER PRIMARY KEY,
  name       TEXT    NOT NULL UNIQUE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE dishes (
  id               INTEGER PRIMARY KEY,
  category_id      INTEGER NOT NULL REFERENCES dish_categories (id),
  name             TEXT    NOT NULL,
  description      TEXT,
  image_path       TEXT,
  pricing_unit     TEXT    NOT NULL
                   CHECK (pricing_unit IN ('per_guest', 'per_tray', 'per_weight', 'per_item')),
  unit_price_minor INTEGER NOT NULL CHECK (unit_price_minor >= 0),
  unit_label       TEXT,
  currency         TEXT    NOT NULL DEFAULT 'ILS',
  is_available     INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0, 1)),
  -- Dietary fields: NULL means unknown and must never be shown as "no" (decision 9).
  kashrut_class    TEXT    CHECK (kashrut_class IN ('meat', 'dairy', 'pareve')),
  is_vegetarian    INTEGER CHECK (is_vegetarian IN (0, 1)),
  is_vegan         INTEGER CHECK (is_vegan IN (0, 1)),
  created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX dishes_category_idx ON dishes (category_id);

CREATE TABLE allergens (
  id   INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

-- A missing row means unknown.
CREATE TABLE dish_allergens (
  dish_id     INTEGER NOT NULL REFERENCES dishes (id) ON DELETE CASCADE,
  allergen_id INTEGER NOT NULL REFERENCES allergens (id),
  status      TEXT    NOT NULL CHECK (status IN ('contains', 'free', 'unknown')),
  PRIMARY KEY (dish_id, allergen_id)
);

CREATE TABLE customers (
  id         INTEGER PRIMARY KEY,
  full_name  TEXT NOT NULL,
  email      TEXT,
  phone      TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE events (
  id                INTEGER PRIMARY KEY,
  customer_id       INTEGER NOT NULL REFERENCES customers (id),
  event_type        TEXT    NOT NULL,
  event_date        TEXT    NOT NULL,
  adults            INTEGER NOT NULL CHECK (adults >= 0),
  children          INTEGER NOT NULL CHECK (children >= 0),
  vegetarian_guests INTEGER NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
  vegan_guests      INTEGER NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),
  restricted_guests INTEGER NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),
  dietary_notes     TEXT,
  CHECK (adults + children > 0)
);

CREATE TABLE orders (
  id                   INTEGER PRIMARY KEY,
  customer_id          INTEGER NOT NULL REFERENCES customers (id),
  event_id             INTEGER NOT NULL UNIQUE REFERENCES events (id),
  status               TEXT    NOT NULL DEFAULT 'draft'
                       CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected')),
  version              INTEGER NOT NULL DEFAULT 1,
  fulfillment_type     TEXT    NOT NULL CHECK (fulfillment_type IN ('pickup', 'delivery')),
  requested_at         TEXT    NOT NULL,
  delivery_address     TEXT,
  subtotal_minor       INTEGER,
  delivery_fee_minor   INTEGER,
  total_minor          INTEGER,
  submitted_at         TEXT,
  decided_at           TEXT,
  decision_note        TEXT,
  created_at           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  CHECK (fulfillment_type = 'pickup' OR delivery_address IS NOT NULL)
);
CREATE INDEX orders_customer_idx ON orders (customer_id);
CREATE INDEX orders_status_idx ON orders (status);

CREATE TABLE order_items (
  id                        INTEGER PRIMARY KEY,
  order_id                  INTEGER NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
  dish_id                   INTEGER NOT NULL REFERENCES dishes (id),
  quantity                  REAL    NOT NULL CHECK (quantity > 0),
  -- Price snapshot, filled on submission; authoritative from pending_approval on.
  snapshot_name             TEXT,
  snapshot_pricing_unit     TEXT,
  snapshot_unit_price_minor INTEGER,
  snapshot_line_total_minor INTEGER,
  UNIQUE (order_id, dish_id)
);
CREATE INDEX order_items_order_idx ON order_items (order_id);
