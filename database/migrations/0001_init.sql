-- Minimal SQLite schema (MVP). Prices are NIS with agorot as decimals; round to 2 places before saving.
-- Run on every connection: PRAGMA foreign_keys = ON;

CREATE TABLE dishes (
  id           INTEGER PRIMARY KEY,
  name         TEXT NOT NULL,
  category     TEXT NOT NULL,
  price_nis    REAL NOT NULL CHECK (price_nis >= 0),
  pricing_unit TEXT NOT NULL CHECK (pricing_unit IN ('per_guest','per_tray','per_weight','per_item')),
  kashrut      TEXT CHECK (kashrut IN ('meat','dairy','pareve')),
  image_path   TEXT,
  is_available INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE customers (
  id        INTEGER PRIMARY KEY,
  full_name TEXT NOT NULL,
  phone     TEXT,
  email     TEXT
);

CREATE TABLE orders (
  id          INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  event_date  TEXT NOT NULL,
  guests      INTEGER NOT NULL CHECK (guests > 0),
  fulfillment TEXT NOT NULL CHECK (fulfillment IN ('pickup','delivery')),
  address     TEXT,
  status      TEXT NOT NULL DEFAULT 'draft'
              CHECK (status IN ('draft','pending_approval','approved','rejected')),
  total_nis   REAL,
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_items (
  id             INTEGER PRIMARY KEY,
  order_id       INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  dish_id        INTEGER NOT NULL REFERENCES dishes(id),
  quantity       REAL NOT NULL CHECK (quantity > 0),
  unit_price_nis REAL NOT NULL CHECK (unit_price_nis >= 0),
  UNIQUE (order_id, dish_id)
);

CREATE TABLE ai_proposals (
  id         INTEGER PRIMARY KEY,
  order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  changes    TEXT NOT NULL CHECK (json_valid(changes)),
  status     TEXT NOT NULL DEFAULT 'pending'
             CHECK (status IN ('pending','approved','rejected')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- A dish with no rows here has unknown allergens, never "allergen-free".
CREATE TABLE allergens (
  dish_id INTEGER NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
  name    TEXT NOT NULL,
  PRIMARY KEY (dish_id, name)
);
