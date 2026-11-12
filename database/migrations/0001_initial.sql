-- Initial schema (SQLite). Translated from docs/DATABASE_SCHEMA.md.
--
-- SQLite translation rules:
--   ids         TEXT, default = 32 random hex chars (seed rows use readable fixed ids)
--   money       INTEGER agorot (1/100 shekel). Never floats. Columns keep the doc names
--               (unit_price, fee, subtotal, ...) but hold agorot, not shekels.
--   quantities  REAL (kg steps like 0.5 are legal), checked > 0
--   enums       TEXT + CHECK (col IN (...))
--   booleans    INTEGER 0/1; NULL = unknown where the doc says so
--   timestamps  TEXT, ISO-8601 UTC, e.g. 2026-11-02T12:00:00Z
--   jsonb       TEXT + CHECK (json_valid(col))
-- Foreign keys are enforced only when the connection sets PRAGMA foreign_keys=ON (app/core/db.py does).
-- The migration runner wraps this file in a transaction. Do not put BEGIN/COMMIT here.

CREATE TABLE customers (
  id          TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  auth_user_id TEXT UNIQUE,                -- reserved for OPEN #1 (accounts); unused for now
  full_name   TEXT NOT NULL,
  email       TEXT,
  phone       TEXT,
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE events (
  id                TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  customer_id       TEXT NOT NULL REFERENCES customers(id),
  event_type        TEXT NOT NULL,
  event_date        TEXT NOT NULL,         -- YYYY-MM-DD
  adults            INTEGER NOT NULL CHECK (adults >= 0),
  children          INTEGER NOT NULL CHECK (children >= 0),
  vegetarian_guests INTEGER NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),  -- OPEN #4
  vegan_guests      INTEGER NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),       -- OPEN #4
  restricted_guests INTEGER NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),
  dietary_notes     TEXT,                  -- free text for the owner; never parsed into safety claims
  CHECK (adults + children > 0)
);
CREATE INDEX events_customer_id ON events(customer_id);

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
  unit_price   INTEGER NOT NULL CHECK (unit_price >= 0),   -- agorot
  unit_label   TEXT,                                       -- OPEN #18
  currency     TEXT NOT NULL DEFAULT 'ILS' CHECK (length(currency) = 3),  -- OPEN #17
  min_quantity REAL CHECK (min_quantity IS NULL OR min_quantity > 0),      -- OPEN #15
  is_available INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0, 1)),
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX dishes_category_id ON dishes(category_id);

-- NULL means "not provided / unknown". It must never be shown as "no".
CREATE TABLE dish_dietary (
  dish_id       TEXT PRIMARY KEY REFERENCES dishes(id) ON DELETE CASCADE,
  kashrut_class TEXT CHECK (kashrut_class IS NULL OR kashrut_class IN ('meat', 'dairy', 'pareve')),
  is_vegetarian INTEGER CHECK (is_vegetarian IS NULL OR is_vegetarian IN (0, 1)),
  is_vegan      INTEGER CHECK (is_vegan IS NULL OR is_vegan IN (0, 1)),
  verified_at   TEXT
);

CREATE TABLE allergens (
  id   INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

-- A missing row means UNKNOWN, which is not the same as 'free'.
CREATE TABLE dish_allergens (
  dish_id     TEXT NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
  allergen_id INTEGER NOT NULL REFERENCES allergens(id),
  status      TEXT NOT NULL CHECK (status IN ('contains', 'free', 'unknown')),
  PRIMARY KEY (dish_id, allergen_id)
);

CREATE TABLE delivery_zones (
  id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  name       TEXT NOT NULL,
  fee        INTEGER NOT NULL CHECK (fee >= 0),            -- agorot
  definition TEXT NOT NULL CHECK (json_valid(definition)), -- shape depends on OPEN #19
  is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE time_slots (
  id               TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  fulfillment_type TEXT NOT NULL CHECK (fulfillment_type IN ('pickup', 'delivery')),
  weekday          INTEGER CHECK (weekday IS NULL OR weekday BETWEEN 0 AND 6),  -- NULL = every day
  start_time       TEXT NOT NULL,                          -- HH:MM
  end_time         TEXT NOT NULL,                          -- HH:MM
  capacity         INTEGER CHECK (capacity IS NULL OR capacity >= 0),           -- OPEN #5
  is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  CHECK (end_time > start_time)
);

CREATE TABLE blocked_dates (
  id     TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  date   TEXT NOT NULL UNIQUE,                             -- YYYY-MM-DD
  reason TEXT
);

CREATE TABLE orders (
  id               TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  customer_id      TEXT NOT NULL REFERENCES customers(id),
  event_id         TEXT NOT NULL UNIQUE REFERENCES events(id),
  status           TEXT NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected')),
  version          INTEGER NOT NULL DEFAULT 1,            -- bumped on every mutation (optimistic lock)
  fulfillment_type TEXT NOT NULL CHECK (fulfillment_type IN ('pickup', 'delivery')),
  requested_at     TEXT NOT NULL,                          -- requested pickup/delivery time (UTC)
  delivery_address TEXT,
  delivery_zone_id TEXT REFERENCES delivery_zones(id),
  subtotal         INTEGER,                                -- agorot; backend-computed, frozen at submission
  delivery_fee     INTEGER,
  total            INTEGER,
  submitted_at     TEXT,
  decided_at       TEXT,
  decision_note    TEXT,
  created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  CHECK (fulfillment_type <> 'delivery' OR (delivery_address IS NOT NULL AND delivery_address <> ''))
);
CREATE INDEX orders_customer_id ON orders(customer_id);
CREATE INDEX orders_status ON orders(status);

CREATE TABLE order_items (
  id                    TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  order_id              TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  dish_id               TEXT NOT NULL REFERENCES dishes(id),
  quantity              REAL NOT NULL CHECK (quantity > 0),
  -- Price snapshot, filled on submission. While draft, prices are read live from dishes.
  snapshot_name         TEXT,
  snapshot_pricing_unit TEXT CHECK (snapshot_pricing_unit IS NULL
                               OR snapshot_pricing_unit IN ('per_guest', 'per_tray', 'per_weight', 'per_item')),
  snapshot_unit_price   INTEGER,                           -- agorot
  snapshot_line_total   INTEGER,                           -- agorot
  UNIQUE (order_id, dish_id)
);

CREATE TABLE ai_conversations (
  id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  order_id   TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX ai_conversations_order_id ON ai_conversations(order_id);

CREATE TABLE ai_messages (
  id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  conversation_id TEXT NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
  content         TEXT NOT NULL CHECK (json_valid(content)),
  created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX ai_messages_conversation_id ON ai_messages(conversation_id);

CREATE TABLE ai_change_proposals (
  id                 TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  order_id           TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  conversation_id    TEXT REFERENCES ai_conversations(id),
  base_order_version INTEGER NOT NULL,                     -- must equal orders.version at execution
  changes            TEXT NOT NULL CHECK (json_valid(changes)),
  price_before       INTEGER NOT NULL,                     -- agorot
  price_after        INTEGER NOT NULL,                     -- agorot
  status             TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'approved', 'rejected', 'expired', 'failed')),
  created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  decided_at         TEXT,
  executed_at        TEXT                                  -- set once: idempotency guard
);
CREATE INDEX ai_change_proposals_order_id ON ai_change_proposals(order_id);
-- Recommendation from the schema doc: at most one pending proposal per order.
CREATE UNIQUE INDEX ai_change_proposals_one_pending
  ON ai_change_proposals(order_id) WHERE status = 'pending';
