-- yumm.ai catering platform: SQLite schema (v1). Design notes: docs/DATABASE_SCHEMA.md
--
-- Conventions
--   * Money is INTEGER agorot (1 shekel = 100). No floats for money. Currency is ILS (OPEN #17).
--   * Dates are TEXT 'YYYY-MM-DD'; times are TEXT 'HH:MM'; timestamps are TEXT ISO-8601 UTC.
--   * Booleans are INTEGER 0/1. NULL on a dietary flag means "unknown" and must never be shown as "no".
--   * Ids exposed through the API (orders, proposals, dishes) are TEXT (uuid in production).
--   * STRICT tables (SQLite >= 3.37). python:3.12-slim ships a newer SQLite.
--   * Foreign keys are OFF by default in SQLite: every connection must run `PRAGMA foreign_keys = ON`.
--   * Application code sets updated_at; there are no triggers.

PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

-- ============================================================================
-- Business configuration
-- ============================================================================

-- Exactly one row. Minimum days between today and the event date (OPEN #5).
CREATE TABLE business_settings (
  id          INTEGER PRIMARY KEY CHECK (id = 1),
  lead_days   INTEGER NOT NULL DEFAULT 2 CHECK (lead_days >= 0),
  updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

-- The event type is required on the order form; the list is owner-editable.
CREATE TABLE event_types (
  id          INTEGER PRIMARY KEY,
  name        TEXT    NOT NULL UNIQUE,
  sort_order  INTEGER NOT NULL DEFAULT 0,
  is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
) STRICT;

-- Delivery is priced per city (OPEN #19 may change the zone definition).
CREATE TABLE delivery_zones (
  id          INTEGER PRIMARY KEY,
  city        TEXT    NOT NULL UNIQUE,
  fee         INTEGER NOT NULL CHECK (fee >= 0),
  is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
) STRICT;

-- The customer picks a window, not an exact time. Capacity per slot is OPEN #5 and is not modelled yet.
CREATE TABLE time_slots (
  id            INTEGER PRIMARY KEY,
  fulfillment   TEXT    NOT NULL CHECK (fulfillment IN ('pickup', 'delivery')),
  start_time    TEXT    NOT NULL CHECK (start_time GLOB '[0-2][0-9]:[0-5][0-9]'),
  end_time      TEXT    NOT NULL CHECK (end_time   GLOB '[0-2][0-9]:[0-5][0-9]'),
  is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  UNIQUE (fulfillment, start_time, end_time),
  CHECK (end_time > start_time)
) STRICT;

-- Dates the business does not take orders for.
CREATE TABLE blocked_dates (
  date    TEXT PRIMARY KEY CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  reason  TEXT
) STRICT;

-- ============================================================================
-- Owner login
-- ============================================================================

CREATE TABLE admin_users (
  id             INTEGER PRIMARY KEY,
  email          TEXT    NOT NULL UNIQUE,
  password_hash  TEXT    NOT NULL,                 -- argon2/bcrypt hash, never the password
  display_name   TEXT,
  is_active      INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  last_login_at  TEXT
) STRICT;

CREATE TABLE admin_sessions (
  token_hash     TEXT    PRIMARY KEY,              -- sha256 of the cookie value; the raw token is never stored
  admin_user_id  INTEGER NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
  created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  expires_at     TEXT    NOT NULL
) STRICT;
CREATE INDEX idx_admin_sessions_user ON admin_sessions(admin_user_id);

-- ============================================================================
-- Catalog
-- ============================================================================

CREATE TABLE dish_categories (
  id          INTEGER PRIMARY KEY,
  slug        TEXT    NOT NULL UNIQUE,             -- stable key used by the frontend, e.g. 'salads'
  name        TEXT    NOT NULL UNIQUE,
  sort_order  INTEGER NOT NULL DEFAULT 0,
  is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
) STRICT;

CREATE TABLE allergens (
  id    INTEGER PRIMARY KEY,
  name  TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE dishes (
  id                    TEXT    PRIMARY KEY,
  category_id           INTEGER NOT NULL REFERENCES dish_categories(id),
  name                  TEXT    NOT NULL,
  description           TEXT,
  image_path            TEXT,
  pricing_unit          TEXT    NOT NULL CHECK (pricing_unit IN ('tray', 'kg', 'item', 'guest')),
  unit_price            INTEGER NOT NULL CHECK (unit_price >= 0),     -- agorot per pricing_unit
  qty_per_guest         REAL    CHECK (qty_per_guest > 0),            -- 'perGuest' in the mock; placeholder until OPEN #3
  step                  REAL    CHECK (step > 0),                     -- quantity increment; NULL = default for the unit
  kashrut               TEXT    CHECK (kashrut IN ('meat', 'dairy', 'pareve')),   -- NULL = not provided
  is_vegetarian         INTEGER CHECK (is_vegetarian IN (0, 1)),                  -- NULL = unknown
  is_vegan              INTEGER CHECK (is_vegan IN (0, 1)),                       -- NULL = unknown
  allergens_verified_at TEXT,                      -- NULL = allergen data unknown (never "safe"); set = dish_allergens is the verified list
  is_available          INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0, 1)),
  sort_order            INTEGER NOT NULL DEFAULT 0,
  created_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  CHECK (is_vegan IS NOT 1 OR is_vegetarian IS 1)  -- a vegan dish is vegetarian
) STRICT;
CREATE INDEX idx_dishes_category ON dishes(category_id, sort_order);

-- Rows list the allergens a dish CONTAINS. Meaningful only when dishes.allergens_verified_at IS NOT NULL:
-- verified + no rows = verified free of the listed allergens; not verified = unknown.
CREATE TABLE dish_allergens (
  dish_id      TEXT    NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
  allergen_id  INTEGER NOT NULL REFERENCES allergens(id),
  PRIMARY KEY (dish_id, allergen_id)
) STRICT, WITHOUT ROWID;

-- ============================================================================
-- Orders
-- ============================================================================

-- One row per order. There are no customer accounts (OPEN #1): the customer is identified by contact
-- details plus a secret status link, so contact data lives on the order.
CREATE TABLE orders (
  id                TEXT    PRIMARY KEY,
  access_token_hash TEXT    NOT NULL UNIQUE,       -- sha256 of the token in the status link; the raw token is shown once
  status            TEXT    NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected')),
  version           INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),   -- +1 on every mutation (optimistic locking)

  -- Contact: collected on the summary screen, so NULL only while draft.
  contact_name      TEXT,
  contact_phone     TEXT,

  -- Event
  event_type_id     INTEGER NOT NULL REFERENCES event_types(id),
  event_date        TEXT    NOT NULL CHECK (event_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  adults            INTEGER NOT NULL CHECK (adults >= 1),
  children          INTEGER NOT NULL DEFAULT 0 CHECK (children >= 0),
  vegetarian_guests INTEGER NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
  vegan_guests      INTEGER NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),
  restricted_guests INTEGER NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),   -- other restriction, e.g. allergy or celiac
  dietary_notes     TEXT,                          -- free text for the owner; never parsed into safety claims
  -- Whether the three dietary counts sit inside adults+children is OPEN #4, so it is validated in the service, not here.

  -- Fulfillment. slot_start/slot_end and city are copied at creation so later edits to time_slots or
  -- delivery_zones do not rewrite existing orders.
  fulfillment       TEXT    NOT NULL CHECK (fulfillment IN ('pickup', 'delivery')),
  slot_id           INTEGER NOT NULL REFERENCES time_slots(id),
  slot_start        TEXT    NOT NULL,
  slot_end          TEXT    NOT NULL,
  delivery_zone_id  INTEGER REFERENCES delivery_zones(id),
  city              TEXT,
  address           TEXT,

  -- Prices in agorot. NULL while draft (priced live from dishes); frozen on submit.
  subtotal          INTEGER CHECK (subtotal >= 0),
  delivery_fee      INTEGER CHECK (delivery_fee >= 0),
  total             INTEGER CHECK (total >= 0),

  submitted_at      TEXT,
  decided_at        TEXT,
  decided_by        INTEGER REFERENCES admin_users(id),
  owner_note        TEXT,                          -- shown to the customer on the status page
  created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

  CHECK (
    (fulfillment = 'delivery' AND delivery_zone_id IS NOT NULL AND city IS NOT NULL AND address IS NOT NULL)
    OR (fulfillment = 'pickup' AND delivery_zone_id IS NULL AND city IS NULL AND address IS NULL)
  ),
  CHECK (
    status = 'draft'
    OR (contact_name IS NOT NULL AND contact_phone IS NOT NULL AND submitted_at IS NOT NULL
        AND subtotal IS NOT NULL AND delivery_fee IS NOT NULL AND total IS NOT NULL)
  ),
  CHECK (total IS NULL OR total = subtotal + delivery_fee),
  CHECK ((status IN ('approved', 'rejected')) = (decided_at IS NOT NULL))
) STRICT;
CREATE INDEX idx_orders_status     ON orders(status, submitted_at);
CREATE INDEX idx_orders_event_date ON orders(event_date);

CREATE TABLE order_items (
  id                    INTEGER PRIMARY KEY,
  order_id              TEXT    NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  dish_id               TEXT    NOT NULL REFERENCES dishes(id),
  quantity              REAL    NOT NULL CHECK (quantity > 0),
  -- Price snapshot: all NULL while draft, all set on submit, and from then on the only source of truth.
  snapshot_name         TEXT,
  snapshot_pricing_unit TEXT    CHECK (snapshot_pricing_unit IN ('tray', 'kg', 'item', 'guest')),
  snapshot_unit_price   INTEGER CHECK (snapshot_unit_price >= 0),
  snapshot_line_total   INTEGER CHECK (snapshot_line_total >= 0),
  UNIQUE (order_id, dish_id),
  CHECK (
    (snapshot_name IS NULL AND snapshot_pricing_unit IS NULL AND snapshot_unit_price IS NULL AND snapshot_line_total IS NULL)
    OR (snapshot_name IS NOT NULL AND snapshot_pricing_unit IS NOT NULL AND snapshot_unit_price IS NOT NULL AND snapshot_line_total IS NOT NULL)
  )
) STRICT;
CREATE INDEX idx_order_items_dish ON order_items(dish_id);

-- Append-only audit trail of status changes (one row on creation, one per transition).
CREATE TABLE order_status_events (
  id             INTEGER PRIMARY KEY,
  order_id       TEXT    NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  from_status    TEXT    CHECK (from_status IN ('draft', 'pending_approval', 'approved', 'rejected')),   -- NULL = creation
  to_status      TEXT    NOT NULL CHECK (to_status IN ('draft', 'pending_approval', 'approved', 'rejected')),
  actor          TEXT    NOT NULL CHECK (actor IN ('customer', 'owner', 'system')),
  admin_user_id  INTEGER REFERENCES admin_users(id),
  note           TEXT,
  created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  CHECK ((actor = 'owner') = (admin_user_id IS NOT NULL))
) STRICT;
CREATE INDEX idx_status_events_order ON order_status_events(order_id, created_at);

-- ============================================================================
-- AI assistant
-- ============================================================================

-- The conversation of an order (one per order). May contain personal data: retention is an open question.
CREATE TABLE ai_messages (
  id          INTEGER PRIMARY KEY,
  order_id    TEXT    NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  role        TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
  content     TEXT    NOT NULL,                    -- plain text; JSON for role 'tool'
  created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;
CREATE INDEX idx_ai_messages_order ON ai_messages(order_id, id);

-- A change the assistant proposes. It only touches the order after the customer approves it, and only
-- if base_order_version still equals orders.version.
CREATE TABLE ai_proposals (
  id                 TEXT    PRIMARY KEY,
  order_id           TEXT    NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  message_id         INTEGER REFERENCES ai_messages(id) ON DELETE SET NULL,   -- the assistant reply that carried it
  base_order_version INTEGER NOT NULL,
  changes            TEXT    NOT NULL CHECK (json_valid(changes)),            -- [{op, dish_id, quantity}], op: add_item | set_quantity | remove_item
  price_before       INTEGER NOT NULL CHECK (price_before >= 0),
  price_after        INTEGER NOT NULL CHECK (price_after >= 0),
  status             TEXT    NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'approved', 'rejected', 'expired', 'failed')),
  created_at         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  decided_at         TEXT,
  executed_at        TEXT,                         -- set once: makes approval idempotent
  CHECK (executed_at IS NULL OR status = 'approved')
) STRICT;
CREATE INDEX idx_ai_proposals_order ON ai_proposals(order_id, status);
