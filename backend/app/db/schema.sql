-- SQLite schema. Money = integer agorot. Dates/times = ISO-8601 TEXT. IDs = app-generated UUID TEXT.
-- NULL in dietary/allergen columns means "unknown", never "no".

CREATE TABLE IF NOT EXISTS customers (
  id TEXT PRIMARY KEY,
  full_name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customers(id),
  event_type TEXT NOT NULL,
  event_date TEXT NOT NULL,
  adults INTEGER NOT NULL CHECK (adults >= 0),
  children INTEGER NOT NULL CHECK (children >= 0),
  vegetarian_guests INTEGER NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
  vegan_guests INTEGER NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),
  restricted_guests INTEGER NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),
  dietary_notes TEXT,
  CHECK (adults + children > 0)
);

CREATE TABLE IF NOT EXISTS dish_categories (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS dishes (
  id TEXT PRIMARY KEY,
  category_id TEXT NOT NULL REFERENCES dish_categories(id),
  name TEXT NOT NULL,
  description TEXT,
  image_path TEXT,
  pricing_unit TEXT NOT NULL CHECK (pricing_unit IN ('per_guest','per_tray','per_weight','per_item')),
  unit_price INTEGER NOT NULL CHECK (unit_price >= 0),
  unit_label TEXT,
  min_quantity REAL,
  is_available INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dishes_category ON dishes(category_id);

CREATE TABLE IF NOT EXISTS dish_dietary (
  dish_id TEXT PRIMARY KEY REFERENCES dishes(id) ON DELETE CASCADE,
  kashrut_class TEXT CHECK (kashrut_class IN ('meat','dairy','pareve')),
  is_vegetarian INTEGER,
  is_vegan INTEGER,
  verified_at TEXT
);

CREATE TABLE IF NOT EXISTS allergens (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

-- Missing row = unknown.
CREATE TABLE IF NOT EXISTS dish_allergens (
  dish_id TEXT NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
  allergen_id INTEGER NOT NULL REFERENCES allergens(id),
  status TEXT NOT NULL CHECK (status IN ('contains','free')),
  PRIMARY KEY (dish_id, allergen_id)
);

CREATE TABLE IF NOT EXISTS delivery_zones (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  fee INTEGER NOT NULL CHECK (fee >= 0),
  definition TEXT NOT NULL CHECK (json_valid(definition)),
  is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS time_slots (
  id TEXT PRIMARY KEY,
  fulfillment_type TEXT NOT NULL CHECK (fulfillment_type IN ('pickup','delivery')),
  weekday INTEGER CHECK (weekday BETWEEN 0 AND 6),
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  capacity INTEGER,
  is_active INTEGER NOT NULL DEFAULT 1,
  CHECK (end_time > start_time)
);

CREATE TABLE IF NOT EXISTS blocked_dates (
  date TEXT PRIMARY KEY,
  reason TEXT
);

CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customers(id),
  event_id TEXT NOT NULL UNIQUE REFERENCES events(id),
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pending_approval','approved','rejected')),
  version INTEGER NOT NULL DEFAULT 1,
  fulfillment_type TEXT NOT NULL CHECK (fulfillment_type IN ('pickup','delivery')),
  requested_at TEXT NOT NULL,
  delivery_address TEXT,
  delivery_zone_id TEXT REFERENCES delivery_zones(id),
  subtotal INTEGER, delivery_fee INTEGER, total INTEGER,
  submitted_at TEXT, decided_at TEXT, decision_note TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK (fulfillment_type <> 'delivery' OR delivery_address IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- snapshot_* are filled on submission and become authoritative then.
CREATE TABLE IF NOT EXISTS order_items (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  dish_id TEXT NOT NULL REFERENCES dishes(id),
  quantity REAL NOT NULL CHECK (quantity > 0),
  snapshot_name TEXT,
  snapshot_pricing_unit TEXT,
  snapshot_unit_price INTEGER,
  snapshot_line_total INTEGER,
  UNIQUE (order_id, dish_id)
);

CREATE TABLE IF NOT EXISTS ai_conversations (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ai_conv_order ON ai_conversations(order_id);

CREATE TABLE IF NOT EXISTS ai_messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user','assistant','tool')),
  content TEXT NOT NULL CHECK (json_valid(content)),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_change_proposals (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  conversation_id TEXT REFERENCES ai_conversations(id),
  base_order_version INTEGER NOT NULL,
  changes TEXT NOT NULL CHECK (json_valid(changes)),
  price_before INTEGER NOT NULL,
  price_after INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','expired','failed')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  decided_at TEXT,
  executed_at TEXT
);
-- At most one pending proposal per order.
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_pending_proposal ON ai_change_proposals(order_id) WHERE status = 'pending';
