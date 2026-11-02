-- SQLite port of docs/DATABASE_SCHEMA.md (draft v0.1).
-- shortcut: no updated_at triggers, set updated_at in app code; add triggers if that gets forgotten.
-- Enums -> CHECK, uuid -> TEXT, bool -> INTEGER 0/1, jsonb -> TEXT with json_valid.
-- shortcut: money is NUMERIC (floats in SQLite), round in app code; switch to integer agorot if totals ever drift.
PRAGMA foreign_keys = ON;

CREATE TABLE customers (
  id           TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  auth_user_id TEXT UNIQUE,
  full_name    TEXT NOT NULL,
  email        TEXT,
  phone        TEXT,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK (email IS NOT NULL OR phone IS NOT NULL)
);

CREATE TABLE events (
  id                TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  customer_id       TEXT NOT NULL REFERENCES customers(id),
  event_type        TEXT NOT NULL,
  event_date        TEXT NOT NULL,
  adults            INTEGER NOT NULL CHECK (adults >= 0),
  children          INTEGER NOT NULL CHECK (children >= 0),
  vegetarian_guests INTEGER NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
  vegan_guests      INTEGER NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),
  restricted_guests INTEGER NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),
  dietary_notes     TEXT,
  event_address     TEXT NOT NULL,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK (adults + children > 0)
);
CREATE INDEX idx_events_customer ON events(customer_id);

CREATE TABLE dish_categories (
  id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  name       TEXT NOT NULL UNIQUE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE dishes (
  id           TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  category_id  TEXT NOT NULL REFERENCES dish_categories(id),
  name         TEXT NOT NULL,
  description  TEXT,
  image_path   TEXT,
  pricing_unit TEXT NOT NULL CHECK (pricing_unit IN ('per_guest','per_tray','per_weight','per_item')),
  unit_price   NUMERIC NOT NULL CHECK (unit_price >= 0),
  unit_label   TEXT,
  currency     TEXT NOT NULL DEFAULT 'ILS' CHECK (length(currency) = 3),
  min_quantity NUMERIC,
  is_available INTEGER NOT NULL DEFAULT 1,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_dishes_category ON dishes(category_id);

-- NULL = unknown (never present as "no").
CREATE TABLE dish_dietary (
  dish_id       TEXT PRIMARY KEY REFERENCES dishes(id) ON DELETE CASCADE,
  kashrut_class TEXT CHECK (kashrut_class IN ('meat','dairy','pareve')),
  is_vegetarian INTEGER CHECK (is_vegetarian IN (0,1)),
  is_vegan      INTEGER CHECK (is_vegan IN (0,1)),
  verified_at   TEXT
);

CREATE TABLE allergens (
  id   INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

-- Missing row = unknown.
CREATE TABLE dish_allergens (
  dish_id     TEXT NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
  allergen_id INTEGER NOT NULL REFERENCES allergens(id),
  status      TEXT NOT NULL CHECK (status IN ('contains','free','unknown')),
  PRIMARY KEY (dish_id, allergen_id)
);

-- A menu = a full meal (set of dishes) sold as one unit, priced per guest.
CREATE TABLE menus (
  id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  name            TEXT NOT NULL,
  description     TEXT,
  price_per_guest NUMERIC NOT NULL CHECK (price_per_guest >= 0),
  is_available    INTEGER NOT NULL DEFAULT 1,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE menu_dishes (
  menu_id TEXT NOT NULL REFERENCES menus(id) ON DELETE CASCADE,
  dish_id TEXT NOT NULL REFERENCES dishes(id),
  PRIMARY KEY (menu_id, dish_id)
);

CREATE TABLE orders (
  id               TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  customer_id      TEXT NOT NULL REFERENCES customers(id),
  event_id         TEXT NOT NULL UNIQUE REFERENCES events(id),
  status           TEXT NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft','pending_approval','approved','rejected')),
  version          INTEGER NOT NULL DEFAULT 1,
  fulfillment_type TEXT NOT NULL CHECK (fulfillment_type IN ('pickup','delivery')),
  requested_at     TEXT NOT NULL,
  subtotal         NUMERIC,
  delivery_fee     NUMERIC,
  total            NUMERIC,
  submitted_at     TEXT,
  decided_at       TEXT,
  decision_note    TEXT,
  created_at       TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_status   ON orders(status);

CREATE TABLE order_items (
  id                    TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  order_id              TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  dish_id               TEXT REFERENCES dishes(id),
  menu_id               TEXT REFERENCES menus(id),
  quantity              NUMERIC NOT NULL CHECK (quantity > 0),
  snapshot_name         TEXT,
  snapshot_pricing_unit TEXT CHECK (snapshot_pricing_unit IN ('per_guest','per_tray','per_weight','per_item')),
  snapshot_unit_price   NUMERIC,
  snapshot_line_total   NUMERIC,
  UNIQUE (order_id, dish_id),
  UNIQUE (order_id, menu_id),
  CHECK ((dish_id IS NULL) <> (menu_id IS NULL)) -- exactly one of dish / menu
);

-- Added beyond the doc: audit trail of status changes.
CREATE TABLE order_status_history (
  id          TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  order_id    TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  from_status TEXT,
  to_status   TEXT NOT NULL,
  actor       TEXT NOT NULL,
  note        TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_status_history_order ON order_status_history(order_id);

CREATE TABLE ai_conversations (
  id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  order_id   TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_ai_conv_order ON ai_conversations(order_id);

CREATE TABLE ai_messages (
  id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  conversation_id TEXT NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('user','assistant','tool')),
  content         TEXT NOT NULL CHECK (json_valid(content)),
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
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
                     CHECK (status IN ('pending','approved','rejected','expired','failed')),
  created_at         TEXT NOT NULL DEFAULT (datetime('now')),
  decided_at         TEXT,
  executed_at        TEXT
);
CREATE INDEX idx_proposals_order ON ai_change_proposals(order_id);
-- One pending proposal per order (doc recommendation).
CREATE UNIQUE INDEX uq_one_pending_proposal ON ai_change_proposals(order_id) WHERE status = 'pending';
