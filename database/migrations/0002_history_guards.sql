-- INSERT OR REPLACE can bypass DELETE triggers when recursive_triggers is off.
-- Refuse conflicting inserts before SQLite deletes an existing ledger entry.
CREATE TRIGGER payments_no_replace BEFORE INSERT ON payments
WHEN EXISTS (SELECT 1 FROM payments WHERE id = NEW.id
             OR (NEW.document_number IS NOT NULL AND document_number = NEW.document_number))
BEGIN
    SELECT RAISE(ABORT, 'payments are append-only; replacement is not allowed');
END;

CREATE TRIGGER equipment_movements_no_replace BEFORE INSERT ON equipment_movements
WHEN EXISTS (SELECT 1 FROM equipment_movements WHERE id = NEW.id)
BEGIN
    SELECT RAISE(ABORT, 'equipment movements are append-only; replacement is not allowed');
END;

CREATE TRIGGER ingredient_movements_no_replace BEFORE INSERT ON ingredient_movements
WHEN EXISTS (SELECT 1 FROM ingredient_movements WHERE id = NEW.id)
BEGIN
    SELECT RAISE(ABORT, 'ingredient movements are append-only; replacement is not allowed');
END;

-- Historical quantities must retain the unit and ingredient they were recorded against.
CREATE TRIGGER ingredients_unit_history BEFORE UPDATE OF base_unit ON ingredients
WHEN NEW.base_unit IS NOT OLD.base_unit
 AND EXISTS (SELECT 1 FROM ingredient_batches b JOIN ingredient_movements m ON m.batch_id = b.id
             WHERE b.ingredient_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'cannot change the unit of recorded stock');
END;

CREATE TRIGGER ingredient_batches_history
BEFORE UPDATE OF ingredient_id, received_on, expires_on ON ingredient_batches
WHEN (NEW.ingredient_id IS NOT OLD.ingredient_id OR NEW.received_on IS NOT OLD.received_on
      OR NEW.expires_on IS NOT OLD.expires_on)
 AND EXISTS (SELECT 1 FROM ingredient_movements WHERE batch_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'cannot rewrite recorded batch identity or dates');
END;

-- Enforce the existing food-drop-off rule for updates on either side of the relation too.
CREATE TRIGGER deliveries_food_requires_delivery_order_update
BEFORE UPDATE OF purpose, order_id ON deliveries
WHEN NEW.purpose = 'food_drop_off'
 AND (SELECT fulfillment_type FROM orders WHERE id = NEW.order_id) IS NOT 'delivery'
BEGIN
    SELECT RAISE(ABORT, 'food drop-off requires a delivery order');
END;

CREATE TRIGGER orders_preserve_food_delivery
BEFORE UPDATE OF fulfillment_type ON orders
WHEN NEW.fulfillment_type <> 'delivery'
 AND EXISTS (SELECT 1 FROM deliveries WHERE order_id = OLD.id AND purpose = 'food_drop_off')
BEGIN
    SELECT RAISE(ABORT, 'food drop-off requires a delivery order');
END;

-- Snapshot destinations so editing an address book does not change delivery history.
-- Existing rows can only be backfilled with the current address, not a lost earlier address.
ALTER TABLE deliveries ADD COLUMN address_snapshot TEXT;

UPDATE deliveries SET address_snapshot = (
    SELECT json_object('street', street, 'house_number', house_number, 'apartment', apartment,
                       'floor', floor, 'city', city, 'postal_code', postal_code,
                       'access_notes', access_notes)
    FROM addresses WHERE id = deliveries.address_id
);

CREATE TRIGGER deliveries_snapshot_insert AFTER INSERT ON deliveries
BEGIN
    UPDATE deliveries SET address_snapshot = (
        SELECT json_object('street', street, 'house_number', house_number, 'apartment', apartment,
                           'floor', floor, 'city', city, 'postal_code', postal_code,
                           'access_notes', access_notes)
        FROM addresses WHERE id = NEW.address_id
    ) WHERE id = NEW.id;
END;

CREATE TRIGGER deliveries_snapshot_edit_guard
BEFORE UPDATE OF address_snapshot ON deliveries
WHEN OLD.address_snapshot IS NOT NULL AND NEW.address_snapshot IS NOT OLD.address_snapshot
BEGIN
    SELECT RAISE(ABORT, 'delivery address snapshots are immutable');
END;

CREATE TRIGGER deliveries_address_edit_guard BEFORE UPDATE OF address_id ON deliveries
WHEN NEW.address_id IS NOT OLD.address_id
BEGIN
    SELECT RAISE(ABORT, 'create a new delivery to change its destination');
END;
