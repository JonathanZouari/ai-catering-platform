PRAGMA foreign_keys = ON;

CREATE TABLE app_settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
) STRICT;

CREATE TABLE dish_categories (
  id         INTEGER PRIMARY KEY,
  slug       TEXT NOT NULL UNIQUE,
  name       TEXT NOT NULL UNIQUE,
  image_path TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
) STRICT;

CREATE TABLE dishes (
  id                   INTEGER PRIMARY KEY,
  category_id          INTEGER NOT NULL REFERENCES dish_categories(id),
  name                 TEXT NOT NULL,
  description          TEXT,
  pricing_unit         TEXT NOT NULL CHECK (pricing_unit IN ('tray','kg','item','guest')),
  unit_price_agorot    INTEGER NOT NULL CHECK (unit_price_agorot >= 0),
  qty_step             REAL NOT NULL DEFAULT 1 CHECK (qty_step > 0),
  min_qty              REAL CHECK (min_qty > 0),
  rec_per_guest        REAL CHECK (rec_per_guest > 0),
  kashrut              TEXT CHECK (kashrut IN ('meat','dairy','pareve')),
  is_vegetarian        INTEGER CHECK (is_vegetarian IN (0,1)),
  is_vegan             INTEGER CHECK (is_vegan IN (0,1)),
  allergens_verified_at TEXT,
  is_available         INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0,1)),
  sort_order           INTEGER NOT NULL DEFAULT 0,
  created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  CHECK (NOT (is_vegan = 1 AND is_vegetarian = 0))
) STRICT;
CREATE INDEX ix_dishes_category ON dishes(category_id);

CREATE TABLE dish_images (
  id         INTEGER PRIMARY KEY,
  dish_id    INTEGER NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
  path       TEXT NOT NULL UNIQUE,
  alt_text   TEXT NOT NULL CHECK (length(trim(alt_text)) > 0),
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  sort_order INTEGER NOT NULL DEFAULT 0
) STRICT;
CREATE INDEX ix_dish_images_dish ON dish_images(dish_id, sort_order);
CREATE UNIQUE INDEX ux_one_primary_image ON dish_images(dish_id) WHERE is_primary = 1;

CREATE TABLE dish_nutrition (
  dish_id         INTEGER PRIMARY KEY REFERENCES dishes(id) ON DELETE CASCADE,
  serving_desc    TEXT,
  serving_g       REAL CHECK (serving_g > 0),
  energy_kcal     REAL CHECK (energy_kcal >= 0),
  protein_g       REAL CHECK (protein_g >= 0),
  carbs_g         REAL CHECK (carbs_g >= 0),
  sugars_g        REAL CHECK (sugars_g >= 0),
  fat_g           REAL CHECK (fat_g >= 0),
  saturated_fat_g REAL CHECK (saturated_fat_g >= 0),
  fiber_g         REAL CHECK (fiber_g >= 0),
  sodium_mg       REAL CHECK (sodium_mg >= 0),
  source          TEXT,
  verified_at     TEXT,
  CHECK (sugars_g <= carbs_g),
  CHECK (saturated_fat_g <= fat_g)
) STRICT;

CREATE TABLE allergens (
  id   INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE label_icons (
  id          INTEGER PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('contains','free_from','dietary')),
  allergen_id INTEGER REFERENCES allergens(id) ON DELETE CASCADE,
  dietary     TEXT CHECK (dietary IN ('vegetarian','vegan','meat','dairy','pareve')),
  path        TEXT NOT NULL,
  alt_text    TEXT NOT NULL CHECK (length(trim(alt_text)) > 0),
  CHECK ((kind = 'dietary') = (dietary IS NOT NULL)),
  CHECK ((kind = 'dietary') = (allergen_id IS NULL)),
  UNIQUE (kind, allergen_id),
  UNIQUE (kind, dietary)
) STRICT;

CREATE TABLE dish_allergens (
  dish_id     INTEGER NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
  allergen_id INTEGER NOT NULL REFERENCES allergens(id),
  PRIMARY KEY (dish_id, allergen_id)
) STRICT, WITHOUT ROWID;

CREATE TABLE delivery_zones (
  id        INTEGER PRIMARY KEY,
  city      TEXT NOT NULL UNIQUE,
  fee_agorot INTEGER NOT NULL CHECK (fee_agorot >= 0),
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
) STRICT;

CREATE TABLE couriers (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  kind          TEXT NOT NULL CHECK (kind IN ('in_house','external')),
  contact_phone TEXT,
  is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
) STRICT;

CREATE TABLE time_slots (
  id               INTEGER PRIMARY KEY,
  fulfillment_type TEXT NOT NULL CHECK (fulfillment_type IN ('pickup','delivery')),
  start_time       TEXT NOT NULL,
  end_time         TEXT NOT NULL,
  is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
  CHECK (end_time > start_time),
  UNIQUE (fulfillment_type, start_time, end_time)
) STRICT;

CREATE TABLE blocked_dates (
  date   TEXT PRIMARY KEY,
  reason TEXT
) STRICT;

CREATE TABLE customers (
  id         INTEGER PRIMARY KEY,
  full_name  TEXT NOT NULL,
  phone      TEXT NOT NULL UNIQUE,
  email      TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
) STRICT;

CREATE TABLE orders (
  id                 INTEGER PRIMARY KEY,
  public_id          TEXT NOT NULL UNIQUE,
  access_token_hash  TEXT NOT NULL,
  customer_id        INTEGER REFERENCES customers(id),
  status             TEXT NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft','pending_approval','approved','rejected')),
  version            INTEGER NOT NULL DEFAULT 1,
  event_type         TEXT,
  event_date         TEXT,
  time_slot_id       INTEGER REFERENCES time_slots(id),
  fulfillment_type   TEXT NOT NULL DEFAULT 'pickup' CHECK (fulfillment_type IN ('pickup','delivery')),
  delivery_zone_id   INTEGER REFERENCES delivery_zones(id),
  delivery_address   TEXT,
  courier_id         INTEGER REFERENCES couriers(id),
  adults             INTEGER NOT NULL DEFAULT 0 CHECK (adults >= 0),
  children           INTEGER NOT NULL DEFAULT 0 CHECK (children >= 0),
  vegetarian_guests  INTEGER NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
  vegan_guests       INTEGER NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),
  restricted_guests  INTEGER NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),
  dietary_notes      TEXT,
  slot_start         TEXT,
  slot_end           TEXT,
  subtotal_agorot    INTEGER,
  delivery_fee_agorot INTEGER,
  total_agorot       INTEGER,
  submitted_at       TEXT,
  decided_at         TEXT,
  decision_note      TEXT,
  created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  CHECK (vegetarian_guests + vegan_guests + restricted_guests <= adults + children),
  CHECK (status = 'draft' OR (
    customer_id IS NOT NULL AND event_type IS NOT NULL AND event_date IS NOT NULL
    AND time_slot_id IS NOT NULL AND adults >= 1 AND total_agorot IS NOT NULL
    AND submitted_at IS NOT NULL AND slot_start IS NOT NULL)),
  CHECK (status = 'draft' OR fulfillment_type = 'pickup'
    OR (delivery_zone_id IS NOT NULL AND delivery_address IS NOT NULL)),
  CHECK (courier_id IS NULL OR fulfillment_type = 'delivery')
) STRICT;
CREATE INDEX ix_orders_status ON orders(status, event_date);
CREATE INDEX ix_orders_customer ON orders(customer_id);

CREATE TABLE order_items (
  order_id                 INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  dish_id                  INTEGER NOT NULL REFERENCES dishes(id),
  quantity                 REAL NOT NULL CHECK (quantity > 0),
  snap_name                TEXT,
  snap_pricing_unit        TEXT,
  snap_unit_price_agorot   INTEGER,
  snap_line_total_agorot   INTEGER,
  PRIMARY KEY (order_id, dish_id)
) STRICT, WITHOUT ROWID;

CREATE TABLE ai_messages (
  id         INTEGER PRIMARY KEY,
  order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  role       TEXT NOT NULL CHECK (role IN ('user','assistant','tool')),
  content    TEXT NOT NULL CHECK (json_valid(content)),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
) STRICT;
CREATE INDEX ix_ai_messages_order ON ai_messages(order_id, id);

CREATE TABLE ai_change_proposals (
  id                  INTEGER PRIMARY KEY,
  public_id           TEXT NOT NULL UNIQUE,
  order_id            INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  message_id          INTEGER REFERENCES ai_messages(id),
  base_order_version  INTEGER NOT NULL,
  changes             TEXT NOT NULL CHECK (json_valid(changes) AND json_type(changes) = 'array'),
  price_before_agorot INTEGER NOT NULL,
  price_after_agorot  INTEGER NOT NULL,
  status              TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','applied','rejected','expired','failed')),
  created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  decided_at          TEXT,
  executed_at         TEXT,
  CHECK ((status = 'applied') = (executed_at IS NOT NULL))
) STRICT;
CREATE UNIQUE INDEX ux_one_pending_proposal ON ai_change_proposals(order_id) WHERE status = 'pending';

CREATE TABLE inventory_items (
  id                INTEGER PRIMARY KEY,
  kind              TEXT NOT NULL CHECK (kind IN ('food','packaging')),
  name              TEXT NOT NULL,
  unit              TEXT NOT NULL CHECK (unit IN ('g','kg','ml','l','unit','pack')),
  qty_on_hand       REAL NOT NULL DEFAULT 0 CHECK (qty_on_hand >= 0),
  reorder_level     REAL CHECK (reorder_level >= 0),
  unit_cost_agorot  INTEGER CHECK (unit_cost_agorot >= 0),
  supplier          TEXT,
  storage           TEXT CHECK (storage IN ('dry','fridge','freezer')),
  is_active         INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
  UNIQUE (kind, name),
  CHECK (storage IS NULL OR kind = 'food')
) STRICT;

CREATE TABLE inventory_movements (
  id          INTEGER PRIMARY KEY,
  item_id     INTEGER NOT NULL REFERENCES inventory_items(id),
  type        TEXT NOT NULL CHECK (type IN ('purchase','usage','waste','adjustment')),
  qty_delta   REAL NOT NULL CHECK (qty_delta <> 0),
  order_id    INTEGER REFERENCES orders(id),
  expires_on  TEXT,
  note        TEXT,
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  CHECK (type <> 'purchase' OR qty_delta > 0),
  CHECK (type NOT IN ('usage','waste') OR qty_delta < 0),
  CHECK (expires_on IS NULL OR type = 'purchase'),
  CHECK (order_id IS NULL OR type = 'usage')
) STRICT;
CREATE INDEX ix_movements_item ON inventory_movements(item_id, created_at);

-- Stock on hand follows the ledger; the CHECK on qty_on_hand rejects a movement that would go below zero.
CREATE TRIGGER trg_movement_applies AFTER INSERT ON inventory_movements
BEGIN
  UPDATE inventory_items SET qty_on_hand = qty_on_hand + NEW.qty_delta WHERE id = NEW.item_id;
END;
