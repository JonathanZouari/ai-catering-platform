-- 0001 — Initial SQLite schema.
--
-- Applied by backend/app/db/migrations.py inside a single transaction, so this file must not
-- contain BEGIN/COMMIT/ROLLBACK or PRAGMA statements. Foreign keys are switched on per
-- connection by backend/app/db/connection.py.
--
-- Conventions (see docs/DATABASE_SCHEMA.md):
--   * STRICT tables: SQLite rejects values of the wrong type instead of coercing them.
--   * Money is INTEGER minor units (agorot for ILS) in columns ending in `_minor`. Never REAL.
--   * Ingredient quantities are INTEGER base units (g, ml, or unit).
--   * Timestamps are UTC TEXT 'YYYY-MM-DDTHH:MM:SSZ'; dates are TEXT 'YYYY-MM-DD'.
--     Both are format-checked, so text comparison orders them correctly.
--   * Booleans are INTEGER 0/1. Enums are TEXT with a CHECK list.
--   * Foreign keys default to NO ACTION (behaves as RESTRICT): history is never cascade-deleted.
--   * Ledgers (payments, equipment_movements, ingredient_movements) are append-only.
--     Corrections are new rows (a refund or an adjustment), never edits.

-- ---------------------------------------------------------------------------------------------
-- People and places
-- ---------------------------------------------------------------------------------------------

CREATE TABLE customers (
    id          INTEGER PRIMARY KEY,
    full_name   TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    email       TEXT COLLATE NOCASE UNIQUE CHECK (email IS NULL OR email LIKE '%_@_%'),
    phone       TEXT CHECK (phone IS NULL OR length(trim(phone)) > 0),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%SZ', updated_at)),
    CHECK (email IS NOT NULL OR phone IS NOT NULL)
) STRICT;

CREATE TABLE employees (
    id          INTEGER PRIMARY KEY,
    full_name   TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    role        TEXT NOT NULL CHECK (role IN (
                    'owner', 'manager', 'chef', 'cook', 'kitchen_assistant', 'driver', 'server', 'other'
                )),
    email       TEXT COLLATE NOCASE UNIQUE CHECK (email IS NULL OR email LIKE '%_@_%'),
    phone       TEXT CHECK (phone IS NULL OR length(trim(phone)) > 0),
    hired_on    TEXT CHECK (hired_on IS NULL OR hired_on IS date(hired_on)),
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%SZ', updated_at))
) STRICT;

-- customer_id NULL = a business address (kitchen, warehouse).
CREATE TABLE addresses (
    id            INTEGER PRIMARY KEY,
    customer_id   INTEGER REFERENCES customers (id),
    label         TEXT,
    street        TEXT NOT NULL CHECK (length(trim(street)) > 0),
    house_number  TEXT,
    apartment     TEXT,
    floor         TEXT,
    city          TEXT NOT NULL CHECK (length(trim(city)) > 0),
    postal_code   TEXT,
    access_notes  TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                  CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                  CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%SZ', updated_at)),
    UNIQUE (id, customer_id)  -- target for orders' (address, customer) foreign key
) STRICT;
CREATE INDEX addresses_customer_id_idx ON addresses (customer_id);

-- ---------------------------------------------------------------------------------------------
-- Events and orders (minimal dependencies for deliveries, payments, and inventory)
-- ---------------------------------------------------------------------------------------------

CREATE TABLE events (
    id                 INTEGER PRIMARY KEY,
    customer_id        INTEGER NOT NULL REFERENCES customers (id),
    event_type         TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
    event_date         TEXT NOT NULL CHECK (event_date IS date(event_date)),
    adults             INTEGER NOT NULL DEFAULT 0 CHECK (adults >= 0),
    children           INTEGER NOT NULL DEFAULT 0 CHECK (children >= 0),
    vegetarian_guests  INTEGER NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
    vegan_guests       INTEGER NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),
    restricted_guests  INTEGER NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),
    dietary_notes      TEXT,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                       CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                       CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%SZ', updated_at)),
    CHECK (adults + children > 0),
    UNIQUE (id, customer_id)  -- target for orders' (event, customer) foreign key
) STRICT;
CREATE INDEX events_customer_id_idx ON events (customer_id);

CREATE TABLE orders (
    id                   INTEGER PRIMARY KEY,
    customer_id          INTEGER NOT NULL REFERENCES customers (id),
    event_id             INTEGER NOT NULL UNIQUE,
    status               TEXT NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected')),
    version              INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    fulfillment_type     TEXT NOT NULL CHECK (fulfillment_type IN ('pickup', 'delivery')),
    requested_at         TEXT NOT NULL
                         CHECK (requested_at IS strftime('%Y-%m-%dT%H:%M:%SZ', requested_at)),
    delivery_address_id  INTEGER,
    currency             TEXT NOT NULL DEFAULT 'ILS'
                         CHECK (length(currency) = 3 AND currency = upper(currency)),
    subtotal_minor       INTEGER CHECK (subtotal_minor IS NULL OR subtotal_minor >= 0),
    delivery_fee_minor   INTEGER CHECK (delivery_fee_minor IS NULL OR delivery_fee_minor >= 0),
    total_minor          INTEGER CHECK (total_minor IS NULL OR total_minor >= 0),
    submitted_at         TEXT CHECK (submitted_at IS NULL
                                     OR submitted_at IS strftime('%Y-%m-%dT%H:%M:%SZ', submitted_at)),
    decided_at           TEXT CHECK (decided_at IS NULL
                                     OR decided_at IS strftime('%Y-%m-%dT%H:%M:%SZ', decided_at)),
    decision_note        TEXT,
    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                         CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    updated_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                         CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%SZ', updated_at)),
    -- The event and the delivery address must belong to the order's customer.
    FOREIGN KEY (event_id, customer_id) REFERENCES events (id, customer_id),
    FOREIGN KEY (delivery_address_id, customer_id) REFERENCES addresses (id, customer_id),
    UNIQUE (id, currency),  -- target for payments' (order, currency) foreign key
    CHECK (fulfillment_type = 'delivery' OR delivery_address_id IS NULL),
    CHECK (fulfillment_type = 'delivery' OR delivery_fee_minor IS NULL OR delivery_fee_minor = 0),
    -- Once submitted, a delivery order needs an address and the price is frozen.
    CHECK (status = 'draft' OR fulfillment_type = 'pickup' OR delivery_address_id IS NOT NULL),
    CHECK (status = 'draft' OR (subtotal_minor IS NOT NULL AND delivery_fee_minor IS NOT NULL
                                AND total_minor IS NOT NULL AND submitted_at IS NOT NULL)),
    CHECK (total_minor IS NULL OR (subtotal_minor IS NOT NULL AND delivery_fee_minor IS NOT NULL
                                   AND total_minor = subtotal_minor + delivery_fee_minor)),
    CHECK ((status IN ('approved', 'rejected')) = (decided_at IS NOT NULL))
) STRICT;
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
CREATE INDEX orders_status_idx ON orders (status);

-- Documented transitions only (DATABASE_SCHEMA.md): draft → pending_approval → approved | rejected.
CREATE TRIGGER orders_status_transition
BEFORE UPDATE OF status ON orders
WHEN NEW.status IS NOT OLD.status
 AND NOT ((OLD.status = 'draft' AND NEW.status = 'pending_approval')
       OR (OLD.status = 'pending_approval' AND NEW.status IN ('approved', 'rejected')))
BEGIN
    SELECT RAISE(ABORT, 'invalid order status transition');
END;

-- ---------------------------------------------------------------------------------------------
-- Deliveries
-- ---------------------------------------------------------------------------------------------

CREATE TABLE deliveries (
    id                  INTEGER PRIMARY KEY,
    order_id            INTEGER NOT NULL REFERENCES orders (id),
    purpose             TEXT NOT NULL DEFAULT 'food_drop_off'
                        CHECK (purpose IN ('food_drop_off', 'equipment_collection')),
    address_id          INTEGER NOT NULL REFERENCES addresses (id),
    driver_employee_id  INTEGER REFERENCES employees (id),
    status              TEXT NOT NULL DEFAULT 'scheduled'
                        CHECK (status IN ('scheduled', 'out_for_delivery', 'delivered', 'failed',
                                          'cancelled')),
    window_start        TEXT NOT NULL
                        CHECK (window_start IS strftime('%Y-%m-%dT%H:%M:%SZ', window_start)),
    window_end          TEXT NOT NULL
                        CHECK (window_end IS strftime('%Y-%m-%dT%H:%M:%SZ', window_end)),
    dispatched_at       TEXT CHECK (dispatched_at IS NULL
                                    OR dispatched_at IS strftime('%Y-%m-%dT%H:%M:%SZ', dispatched_at)),
    completed_at        TEXT CHECK (completed_at IS NULL
                                    OR completed_at IS strftime('%Y-%m-%dT%H:%M:%SZ', completed_at)),
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                        CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                        CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%SZ', updated_at)),
    UNIQUE (id, order_id),  -- target for equipment_movements' (delivery, order) foreign key
    CHECK (window_end > window_start),
    CHECK (status NOT IN ('out_for_delivery', 'delivered')
           OR (driver_employee_id IS NOT NULL AND dispatched_at IS NOT NULL)),
    CHECK ((status IN ('delivered', 'failed')) = (completed_at IS NOT NULL)),
    CHECK (completed_at IS NULL OR dispatched_at IS NULL OR completed_at >= dispatched_at)
) STRICT;
CREATE INDEX deliveries_order_id_idx ON deliveries (order_id);
CREATE INDEX deliveries_driver_idx ON deliveries (driver_employee_id, window_start);
CREATE INDEX deliveries_schedule_idx ON deliveries (status, window_start);

CREATE TRIGGER deliveries_food_requires_delivery_order
BEFORE INSERT ON deliveries
WHEN NEW.purpose = 'food_drop_off'
 AND (SELECT fulfillment_type FROM orders WHERE id = NEW.order_id) IS NOT 'delivery'
BEGIN
    SELECT RAISE(ABORT, 'food drop-off requires a delivery order');
END;

-- ---------------------------------------------------------------------------------------------
-- Income receipts and refunds (append-only ledger)
-- ---------------------------------------------------------------------------------------------

CREATE TABLE payments (
    id                       INTEGER PRIMARY KEY,
    kind                     TEXT NOT NULL CHECK (kind IN ('receipt', 'refund')),
    order_id                 INTEGER NOT NULL,
    currency                 TEXT NOT NULL CHECK (length(currency) = 3 AND currency = upper(currency)),
    amount_minor             INTEGER NOT NULL CHECK (amount_minor > 0),  -- sign comes from kind
    method                   TEXT NOT NULL CHECK (method IN (
                                 'cash', 'credit_card', 'bank_transfer', 'bit', 'check', 'other'
                             )),
    document_number          TEXT UNIQUE
                             CHECK (document_number IS NULL OR length(trim(document_number)) > 0),
    refund_of_payment_id     INTEGER,
    reason                   TEXT,
    recorded_by_employee_id  INTEGER REFERENCES employees (id),
    occurred_at              TEXT NOT NULL
                             CHECK (occurred_at IS strftime('%Y-%m-%dT%H:%M:%SZ', occurred_at)),
    created_at               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                             CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    -- Same currency as the order; a refund belongs to the same order and currency as its receipt.
    FOREIGN KEY (order_id, currency) REFERENCES orders (id, currency),
    FOREIGN KEY (refund_of_payment_id, order_id, currency)
        REFERENCES payments (id, order_id, currency),
    UNIQUE (id, order_id, currency),
    CHECK ((kind = 'refund') = (refund_of_payment_id IS NOT NULL)),
    CHECK (kind = 'receipt' OR coalesce(length(trim(reason)), 0) > 0)
) STRICT;
CREATE INDEX payments_order_id_idx ON payments (order_id);
CREATE INDEX payments_refund_of_idx ON payments (refund_of_payment_id);

CREATE TRIGGER payments_refund_targets_receipt
BEFORE INSERT ON payments
WHEN NEW.kind = 'refund'
 AND (SELECT kind FROM payments WHERE id = NEW.refund_of_payment_id) IS NOT 'receipt'
BEGIN
    SELECT RAISE(ABORT, 'a refund must reference a receipt');
END;

CREATE TRIGGER payments_refund_within_receipt
BEFORE INSERT ON payments
WHEN NEW.kind = 'refund'
 AND NEW.amount_minor
     + (SELECT coalesce(sum(amount_minor), 0) FROM payments
        WHERE refund_of_payment_id = NEW.refund_of_payment_id)
     > (SELECT amount_minor FROM payments WHERE id = NEW.refund_of_payment_id)
BEGIN
    SELECT RAISE(ABORT, 'refunds exceed the original receipt');
END;

CREATE TRIGGER payments_no_update BEFORE UPDATE ON payments
BEGIN
    SELECT RAISE(ABORT, 'payments are append-only; record a refund instead');
END;

CREATE TRIGGER payments_no_delete BEFORE DELETE ON payments
BEGIN
    SELECT RAISE(ABORT, 'payments are append-only; record a refund instead');
END;

CREATE VIEW order_payment_summary AS
SELECT
    o.id AS order_id,
    o.currency,
    o.total_minor,
    coalesce(sum(CASE WHEN p.kind = 'receipt' THEN p.amount_minor END), 0) AS received_minor,
    coalesce(sum(CASE WHEN p.kind = 'refund' THEN p.amount_minor END), 0) AS refunded_minor,
    coalesce(sum(CASE WHEN p.kind = 'receipt' THEN p.amount_minor ELSE -p.amount_minor END), 0)
        AS net_paid_minor,
    o.total_minor
        - coalesce(sum(CASE WHEN p.kind = 'receipt' THEN p.amount_minor ELSE -p.amount_minor END), 0)
        AS balance_due_minor
FROM orders AS o
LEFT JOIN payments AS p ON p.order_id = o.id
GROUP BY o.id;

-- ---------------------------------------------------------------------------------------------
-- Reusable equipment: tables and serving utensils
-- ---------------------------------------------------------------------------------------------

CREATE TABLE equipment_items (
    id                      INTEGER PRIMARY KEY,
    name                    TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK (length(trim(name)) > 0),
    category                TEXT NOT NULL CHECK (category IN ('table', 'serving_utensil')),
    description             TEXT,
    replacement_cost_minor  INTEGER CHECK (replacement_cost_minor IS NULL
                                           OR replacement_cost_minor >= 0),
    is_active               INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                            CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                            CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%SZ', updated_at))
) STRICT;

-- Effect of each movement type (quantity is always positive):
--   purchase       on hand +q
--   dispatch       on hand -q, out at the order's event +q
--   return         on hand +q, out at the order's event -q
--   lost_at_event                out at the order's event -q   (lost or broken at the event)
--   write_off      on hand -q                                  (lost or broken in storage)
--   adjustment_in  on hand +q   (stock count correction)
--   adjustment_out on hand -q   (stock count correction)
CREATE TABLE equipment_movements (
    id                 INTEGER PRIMARY KEY,
    equipment_item_id  INTEGER NOT NULL REFERENCES equipment_items (id),
    movement_type      TEXT NOT NULL CHECK (movement_type IN (
                           'purchase', 'dispatch', 'return', 'lost_at_event', 'write_off',
                           'adjustment_in', 'adjustment_out'
                       )),
    quantity           INTEGER NOT NULL CHECK (quantity > 0),
    order_id           INTEGER REFERENCES orders (id),
    delivery_id        INTEGER,
    employee_id        INTEGER REFERENCES employees (id),
    occurred_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                       CHECK (occurred_at IS strftime('%Y-%m-%dT%H:%M:%SZ', occurred_at)),
    notes              TEXT,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                       CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    FOREIGN KEY (delivery_id, order_id) REFERENCES deliveries (id, order_id),
    CHECK ((movement_type IN ('dispatch', 'return', 'lost_at_event')) = (order_id IS NOT NULL)),
    CHECK (delivery_id IS NULL OR order_id IS NOT NULL),
    CHECK (movement_type NOT IN ('lost_at_event', 'write_off', 'adjustment_in', 'adjustment_out')
           OR coalesce(length(trim(notes)), 0) > 0)
) STRICT;
CREATE INDEX equipment_movements_item_idx ON equipment_movements (equipment_item_id, occurred_at);
CREATE INDEX equipment_movements_order_idx ON equipment_movements (order_id);

CREATE VIEW equipment_stock AS
SELECT
    i.id AS equipment_item_id,
    i.name,
    i.category,
    coalesce(sum(CASE m.movement_type
        WHEN 'purchase' THEN m.quantity
        WHEN 'return' THEN m.quantity
        WHEN 'adjustment_in' THEN m.quantity
        WHEN 'dispatch' THEN -m.quantity
        WHEN 'write_off' THEN -m.quantity
        WHEN 'adjustment_out' THEN -m.quantity
        ELSE 0 END), 0) AS on_hand,
    coalesce(sum(CASE m.movement_type
        WHEN 'dispatch' THEN m.quantity
        WHEN 'return' THEN -m.quantity
        WHEN 'lost_at_event' THEN -m.quantity
        ELSE 0 END), 0) AS out_at_events
FROM equipment_items AS i
LEFT JOIN equipment_movements AS m ON m.equipment_item_id = i.id
GROUP BY i.id;

CREATE VIEW equipment_out_by_order AS
SELECT
    equipment_item_id,
    order_id,
    sum(CASE movement_type WHEN 'dispatch' THEN quantity ELSE -quantity END) AS quantity_out
FROM equipment_movements
WHERE order_id IS NOT NULL
GROUP BY equipment_item_id, order_id;

CREATE TRIGGER equipment_movements_on_hand_not_negative
BEFORE INSERT ON equipment_movements
WHEN NEW.movement_type IN ('dispatch', 'write_off', 'adjustment_out')
 AND (SELECT on_hand FROM equipment_stock WHERE equipment_item_id = NEW.equipment_item_id)
     < NEW.quantity
BEGIN
    SELECT RAISE(ABORT, 'not enough equipment on hand');
END;

CREATE TRIGGER equipment_movements_out_not_negative
BEFORE INSERT ON equipment_movements
WHEN NEW.movement_type IN ('return', 'lost_at_event')
 AND coalesce((SELECT quantity_out FROM equipment_out_by_order
               WHERE equipment_item_id = NEW.equipment_item_id AND order_id = NEW.order_id), 0)
     < NEW.quantity
BEGIN
    SELECT RAISE(ABORT, 'more equipment returned or lost than was dispatched for this order');
END;

CREATE TRIGGER equipment_movements_no_update BEFORE UPDATE ON equipment_movements
BEGIN
    SELECT RAISE(ABORT, 'equipment movements are append-only; record an adjustment instead');
END;

CREATE TRIGGER equipment_movements_no_delete BEFORE DELETE ON equipment_movements
BEGIN
    SELECT RAISE(ABORT, 'equipment movements are append-only; record an adjustment instead');
END;

-- ---------------------------------------------------------------------------------------------
-- Raw ingredients, batches with expiry dates, and movements
-- ---------------------------------------------------------------------------------------------

CREATE TABLE ingredients (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK (length(trim(name)) > 0),
    base_unit      TEXT NOT NULL CHECK (base_unit IN ('g', 'ml', 'unit')),
    reorder_level  INTEGER CHECK (reorder_level IS NULL OR reorder_level >= 0),  -- in base_unit
    is_active      INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                   CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                   CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%SZ', updated_at))
) STRICT;

-- expires_on NULL = non-perishable. Quantity lives only in ingredient_movements.
CREATE TABLE ingredient_batches (
    id                INTEGER PRIMARY KEY,
    ingredient_id     INTEGER NOT NULL REFERENCES ingredients (id),
    lot_code          TEXT CHECK (lot_code IS NULL OR length(trim(lot_code)) > 0),
    supplier_name     TEXT,
    received_on       TEXT NOT NULL CHECK (received_on IS date(received_on)),
    expires_on        TEXT CHECK (expires_on IS NULL OR expires_on IS date(expires_on)),
    total_cost_minor  INTEGER CHECK (total_cost_minor IS NULL OR total_cost_minor >= 0),
    currency          TEXT NOT NULL DEFAULT 'ILS'
                      CHECK (length(currency) = 3 AND currency = upper(currency)),
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                      CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    UNIQUE (ingredient_id, lot_code),
    CHECK (expires_on IS NULL OR expires_on >= received_on)
) STRICT;
CREATE INDEX ingredient_batches_expiry_idx ON ingredient_batches (ingredient_id, expires_on);

CREATE TABLE ingredient_movements (
    id             INTEGER PRIMARY KEY,
    batch_id       INTEGER NOT NULL REFERENCES ingredient_batches (id),
    movement_type  TEXT NOT NULL CHECK (movement_type IN (
                       'receipt', 'consumption', 'waste', 'expired_disposal',
                       'return_to_supplier', 'adjustment_in', 'adjustment_out'
                   )),
    quantity       INTEGER NOT NULL CHECK (quantity > 0),  -- in the ingredient's base_unit
    order_id       INTEGER REFERENCES orders (id),
    employee_id    INTEGER REFERENCES employees (id),
    occurred_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                   CHECK (occurred_at IS strftime('%Y-%m-%dT%H:%M:%SZ', occurred_at)),
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                   CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    CHECK (movement_type IN ('consumption', 'waste') OR order_id IS NULL),
    CHECK (movement_type NOT IN ('waste', 'adjustment_in', 'adjustment_out')
           OR coalesce(length(trim(notes)), 0) > 0)
) STRICT;
CREATE INDEX ingredient_movements_batch_idx ON ingredient_movements (batch_id, occurred_at);
CREATE INDEX ingredient_movements_order_idx ON ingredient_movements (order_id);

CREATE VIEW ingredient_batch_stock AS
SELECT
    b.id AS batch_id,
    b.ingredient_id,
    i.name AS ingredient_name,
    i.base_unit,
    b.lot_code,
    b.received_on,
    b.expires_on,
    coalesce(sum(CASE
        WHEN m.movement_type IN ('receipt', 'adjustment_in') THEN m.quantity
        WHEN m.movement_type IS NULL THEN 0
        ELSE -m.quantity END), 0) AS on_hand
FROM ingredient_batches AS b
JOIN ingredients AS i ON i.id = b.ingredient_id
LEFT JOIN ingredient_movements AS m ON m.batch_id = b.id
GROUP BY b.id;

-- Expiry is judged against the current UTC date when the view is read.
CREATE VIEW ingredient_stock AS
SELECT
    i.id AS ingredient_id,
    i.name,
    i.base_unit,
    i.reorder_level,
    coalesce(sum(CASE WHEN s.expires_on IS NULL OR s.expires_on >= date('now')
                      THEN s.on_hand END), 0) AS usable_on_hand,
    coalesce(sum(CASE WHEN s.expires_on < date('now') THEN s.on_hand END), 0) AS expired_on_hand
FROM ingredients AS i
LEFT JOIN ingredient_batch_stock AS s ON s.ingredient_id = i.id
GROUP BY i.id;

CREATE TRIGGER ingredient_movements_not_before_receipt
BEFORE INSERT ON ingredient_movements
WHEN date(NEW.occurred_at) < (SELECT received_on FROM ingredient_batches WHERE id = NEW.batch_id)
BEGIN
    SELECT RAISE(ABORT, 'movement is dated before the batch was received');
END;

CREATE TRIGGER ingredient_movements_on_hand_not_negative
BEFORE INSERT ON ingredient_movements
WHEN NEW.movement_type NOT IN ('receipt', 'adjustment_in')
 AND (SELECT on_hand FROM ingredient_batch_stock WHERE batch_id = NEW.batch_id) < NEW.quantity
BEGIN
    SELECT RAISE(ABORT, 'not enough of this batch on hand');
END;

CREATE TRIGGER ingredient_movements_no_expired_consumption
BEFORE INSERT ON ingredient_movements
WHEN NEW.movement_type = 'consumption'
 AND date(NEW.occurred_at) > (SELECT expires_on FROM ingredient_batches WHERE id = NEW.batch_id)
BEGIN
    SELECT RAISE(ABORT, 'cannot consume an expired batch');
END;

CREATE TRIGGER ingredient_movements_no_update BEFORE UPDATE ON ingredient_movements
BEGIN
    SELECT RAISE(ABORT, 'ingredient movements are append-only; record an adjustment instead');
END;

CREATE TRIGGER ingredient_movements_no_delete BEFORE DELETE ON ingredient_movements
BEGIN
    SELECT RAISE(ABORT, 'ingredient movements are append-only; record an adjustment instead');
END;

-- ---------------------------------------------------------------------------------------------
-- updated_at maintenance (skipped when the statement sets updated_at itself)
-- ---------------------------------------------------------------------------------------------

CREATE TRIGGER customers_touch AFTER UPDATE ON customers WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE customers SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;

CREATE TRIGGER employees_touch AFTER UPDATE ON employees WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE employees SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;

CREATE TRIGGER addresses_touch AFTER UPDATE ON addresses WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE addresses SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;

CREATE TRIGGER events_touch AFTER UPDATE ON events WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE events SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;

CREATE TRIGGER orders_touch AFTER UPDATE ON orders WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE orders SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;

CREATE TRIGGER deliveries_touch AFTER UPDATE ON deliveries WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE deliveries SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;

CREATE TRIGGER equipment_items_touch AFTER UPDATE ON equipment_items
WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE equipment_items SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    WHERE id = NEW.id;
END;

CREATE TRIGGER ingredients_touch AFTER UPDATE ON ingredients WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE ingredients SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;
